// 「影视观看榜」维度定义 + 数据汇总（9+1 电视剧评分框架）
// 9 个基础维度各 1-10 分（合计 90 分）+ 好创新加分（最高 10 分）= 总分上限 100 分
import { FILM_PART1 } from './film_part1.js'
import { FILM_PART2 } from './film_part2.js'
import { FILM_PART2B } from './film_part2b.js'
import { FILM_PART3 } from './film_part3.js'
import { FILM_PART4 } from './film_part4.js'
import { FILM_PART5 } from './film_part5.js'

export const FILM_DIMS = [
  '好老板',
  '好故事',
  '好团队',
  '好演员',
  '好制作',
  '好宣发',
  '好风口',
  '好票房',
  '好口碑',
  '好创新',
]

export const FILM_RANK = (() => {
  const all = [
    ...FILM_PART1,
    ...FILM_PART2,
    ...FILM_PART2B,
    ...FILM_PART3,
    ...FILM_PART4,
    ...FILM_PART5,
  ]
  // 去重：同名作品（跨分片可能重复）只保留第一条
  const seen = new Set()
  return all.filter((x) => {
    if (seen.has(x.name)) return false
    seen.add(x.name)
    return true
  })
})()
