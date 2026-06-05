/**
 * migrate_to_supabase.js - 迁移数据到 Supabase
 *
 * 前提条件：
 * 1. 在 Supabase SQL Editor 执行 supabase-schema.sql 建表
 * 2. 确认 .env.local 中的 Supabase 凭据正确
 *
 * 用法：
 *   node scripts/migrate_to_supabase.js [--all] [--funds] [--tougu] [--skip-clean]
 */
import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || 'YOUR_ANON_KEY'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// 数据文件路径
const FUNDS_NDJSON = resolve(__dirname, '..', '..', 'asset-config-miniapp', 'scripts', 'funds_full.ndjson')
const TOUGU_NDJSON = resolve(__dirname, '..', '..', 'asset-config-miniapp', 'scripts', 'tougu_products.ndjson')

const BATCH_SIZE = 500

function parseArgs() {
  const args = process.argv.slice(2)
  const opts = { all: false, funds: false, tougu: false, skipClean: false }
  if (args.includes('--all') || args.length === 0) opts.all = true
  if (args.includes('--funds')) opts.funds = true
  if (args.includes('--tougu')) opts.tougu = true
  if (args.includes('--skip-clean')) opts.skipClean = true
  return opts
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

async function deleteAll(table) {
  // Supabase REST API 不支持无条件删除，用 RPC 或逐步删除
  // 方案：先查出所有 id，再批量删除
  const { data, error } = await supabase.from(table).select('id').limit(10000)
  if (error) {
    console.log(`  清空失败: ${error.message}`)
    return
  }
  if (!data || data.length === 0) {
    console.log('  表已为空')
    return
  }
  const ids = data.map(d => d.id)
  // 分批删除
  const chunkSize = 500
  for (let i = 0; i < ids.length; i += chunkSize) {
    const chunk = ids.slice(i, i + chunkSize)
    await supabase.from(table).delete().in('id', chunk)
  }
  console.log(`  已清空 ${ids.length} 条旧数据`)
}

async function insertBatch(table, rows) {
  const { error } = await supabase.from(table).insert(rows)
  if (error) {
    console.log(`  插入失败: ${error.message}`)
    return 0
  }
  return rows.length
}

async function migrateFunds(skipClean) {
  if (!existsSync(FUNDS_NDJSON)) {
    console.log(`  文件不存在: ${FUNDS_NDJSON}`)
    return 0
  }

  const content = readFileSync(FUNDS_NDJSON, 'utf-8')
  const lines = content.split('\n').filter(l => l.trim())
  console.log(`  数据源: ${FUNDS_NDJSON}`)
  console.log(`  总记录: ${lines.length}条`)

  if (!skipClean) {
    console.log('  清空旧 fund_scores 数据...')
    await deleteAll('fund_scores')
    await sleep(500)
  }

  let batch = []
  let batchNum = 0
  let totalInserted = 0

  for (const line of lines) {
    try {
      const doc = JSON.parse(line)
      delete doc._id
      batch.push(doc)
    } catch (e) {
      console.log(`  JSON 解析失败: ${e.message}`)
    }

    if (batch.length >= BATCH_SIZE) {
      batchNum++
      const inserted = await insertBatch('fund_scores', batch)
      totalInserted += inserted
      process.stdout.write(`  第${batchNum}批: 插入${inserted}条（累计${totalInserted}/${lines.length}）\n`)
      batch = []
      await sleep(100)
    }
  }

  if (batch.length > 0) {
    batchNum++
    const inserted = await insertBatch('fund_scores', batch)
    totalInserted += inserted
    process.stdout.write(`  第${batchNum}批: 插入${inserted}条（累计${totalInserted}/${lines.length}）\n`)
  }

  return totalInserted
}

async function migrateTougu(skipClean) {
  if (!existsSync(TOUGU_NDJSON)) {
    console.log(`  文件不存在: ${TOUGU_NDJSON}`)
    return 0
  }

  const content = readFileSync(TOUGU_NDJSON, 'utf-8')
  const lines = content.split('\n').filter(l => l.trim())
  console.log(`  数据源: ${TOUGU_NDJSON}`)
  console.log(`  总记录: ${lines.length}条`)

  if (!skipClean) {
    console.log('  清空旧 tougu_products 数据...')
    await deleteAll('tougu_products')
    await sleep(500)
  }

  const TOUGU_COLUMNS = new Set([
    'name', 'company', 'type', 'typeName', 'desc', 'tags',
    'return3m', 'return1y', 'maxDrawdown', 'url', 'updateDate', 'dataSource'
  ])

  const allRows = []
  for (const line of lines) {
    try {
      const doc = JSON.parse(line)
      delete doc._id
      const cleaned = {}
      for (const [k, v] of Object.entries(doc)) {
        if (TOUGU_COLUMNS.has(k)) cleaned[k] = v
      }
      // tags 处理
      if (typeof cleaned.tags === 'string') {
        cleaned.tags = cleaned.tags.split(/\s+/).filter(Boolean)
      } else if (!cleaned.tags) {
        cleaned.tags = []
      }
      allRows.push(cleaned)
    } catch (e) {
      console.log(`  JSON 解析失败: ${e.message}`)
    }
  }

  const inserted = await insertBatch('tougu_products', allRows)
  console.log(`  插入${inserted}条投顾产品`)
  return inserted
}

import { existsSync } from 'fs'

async function insertFundMeta(navDate, totalCount, scoredCount) {
  const { error } = await supabase.from('fund_scores_meta').insert({
    update_time: new Date().toISOString().replace('T', ' ').slice(0, 19),
    total_count: totalCount,
    scored_count: scoredCount,
    nav_date: navDate,
  })
  if (error) {
    console.log(`  元信息写入失败: ${error.message}`)
  } else {
    console.log(`  写入元信息: 总数${totalCount}, 有分${scoredCount}, 日期${navDate}`)
  }
}

async function main() {
  const opts = parseArgs()

  console.log('='.repeat(55))
  console.log('  微信云数据库 → Supabase 数据迁移')
  console.log(`  目标: ${SUPABASE_URL}`)
  console.log('='.repeat(55))

  // 先测试连接
  const { error } = await supabase.from('config').select('id').limit(1)
  if (error) {
    if (error.message.includes('Could not find') || error.code === '42P01') {
      console.log('\n❌ 表不存在！请先执行建表 SQL：')
      console.log('   https://supabase.com/dashboard/project/tqhtegazxykkqfcpejky/sql')
      console.log('   复制 supabase-schema.sql 的内容执行\n')
      process.exit(1)
    }
    console.log(`\n❌ 连接失败: ${error.message}\n`)
    process.exit(1)
  }
  console.log('✅ 连接成功\n')

  if (opts.all || opts.funds) {
    console.log('[fund_scores] 迁移靠谱基金数据...')
    const count = await migrateFunds(opts.skipClean)
    console.log(`  完成: ${count}条\n`)
  }

  if (opts.all || opts.tougu) {
    console.log('[tougu_products] 迁移投顾产品数据...')
    const count = await migrateTougu(opts.skipClean)
    console.log(`  完成: ${count}条\n`)
  }

  console.log('='.repeat(55))
  console.log('  迁移完成!')
  console.log('='.repeat(55))
}

main().catch(e => {
  console.error('迁移失败:', e)
  process.exit(1)
})
