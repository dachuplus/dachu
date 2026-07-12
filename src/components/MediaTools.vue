<template>
  <div class="media-tools">
    <!-- 子工具切换 -->
    <div class="mt-subtabs">
      <div
        class="mt-subtab"
        :class="{ active: sub === 'v2a' }"
        @click="sub = 'v2a'"
      >MP4 转 MP3</div>
      <div
        class="mt-subtab"
        :class="{ active: sub === 'a2v' }"
        @click="sub = 'a2v'"
      >MP3 + 图片 合成 MP4</div>
    </div>

    <p class="mt-note">全部转换在您的浏览器本地完成，文件不会上传到任何服务器，请放心使用。单个上传文件不超过 30MB。</p>

    <!-- ========== MP4 → MP3 ========== -->
    <div v-if="sub === 'v2a'" class="mt-card">
      <div class="mt-card-title">MP4 转 MP3</div>
      <label class="mt-drop" :class="{ filled: v2aFile }">
        <input type="file" accept="video/mp4,video/*" @change="onV2aFile" hidden />
        <span v-if="!v2aFile">点击选择 MP4 视频文件</span>
        <span v-else>已选择：{{ v2aFile.name }}（{{ fmtSize(v2aFile.size) }}）</span>
      </label>

      <button
        class="mt-btn"
        :disabled="!v2aFile || busy"
        @click="convertV2A"
      >{{ busy && task === 'v2a' ? '转换中…' : '开始转换为 MP3' }}</button>

      <div v-if="busy && task === 'v2a'" class="mt-progress">
        <div class="mt-progress-bar" :style="{ width: progress + '%' }"></div>
        <span class="mt-progress-txt">{{ progress }}%</span>
      </div>

      <div v-if="v2aResult" class="mt-result">
        <a :href="v2aResult.url" :download="v2aResult.name" class="mt-download">下载 MP3（{{ fmtSize(v2aResult.size) }}）</a>
      </div>
    </div>

    <!-- ========== MP3 + 图片 → MP4 ========== -->
    <div v-if="sub === 'a2v'" class="mt-card">
      <div class="mt-card-title">MP3 + 图片 合成 MP4</div>

      <label class="mt-drop" :class="{ filled: a2vAudio }">
        <input type="file" accept="audio/mpeg,audio/*" @change="onA2vAudio" hidden />
        <span v-if="!a2vAudio">点击选择 MP3 音频文件</span>
        <span v-else>音频：{{ a2vAudio.name }}（{{ fmtSize(a2vAudio.size) }}{{ a2vAudioDuration ? ' / 约 ' + a2vAudioDuration.toFixed(0) + 's' : '' }}）</span>
      </label>

      <label class="mt-drop" :class="{ filled: a2vImages.length }">
        <input type="file" accept="image/*" multiple @change="onA2vImages" hidden />
        <span v-if="!a2vImages.length">点击选择图片（可多选，多张图片将在视频中循环播放）</span>
        <span v-else>已选择 {{ a2vImages.length }} 张图片</span>
      </label>

      <div v-if="a2vImages.length" class="mt-thumbs">
        <div v-for="(img, idx) in a2vImages" :key="idx" class="mt-thumb">
          <span class="mt-thumb-idx">{{ idx + 1 }}</span>
          <img :src="img.url" alt="预览" />
          <button type="button" class="mt-thumb-del" @click="removeA2vImage(idx)" title="移除">×</button>
        </div>
      </div>

      <div v-if="a2vImages.length" class="mt-row">
        <label class="mt-inline-label">每张图片显示时长（秒）</label>
        <input type="number" min="1" max="30" step="1" v-model.number="a2vPerImgSec" class="mt-num" />
        <span class="mt-hint-inline">{{ a2vLoopInfo }}</span>
      </div>

      <!-- 字幕来源切换 -->
      <div class="mt-sub-block">
        <div class="mt-sub-modes">
          <label class="mt-radio"><input type="radio" value="upload" v-model="a2vSubMode" /> 上传字幕文件</label>
          <label class="mt-radio"><input type="radio" value="paste" v-model="a2vSubMode" /> 粘贴歌词生成字幕</label>
        </div>

        <label v-if="a2vSubMode === 'upload'" class="mt-drop mt-sub-drop" :class="{ filled: a2vSubtitle }">
          <input type="file" accept=".srt,.vtt,.ass,.ssa,text/plain" @change="onA2vSubtitle" hidden />
          <span v-if="!a2vSubtitle">（可选）点击上传字幕文件（SRT / VTT / ASS / SSA）</span>
          <span v-else>字幕：{{ a2vSubtitle.name }}（{{ fmtSize(a2vSubtitle.size) }}）</span>
        </label>

        <div v-else class="mt-paste-block">
          <textarea
            v-model="a2vLyricsText"
            class="mt-textarea"
            placeholder="把歌词粘贴到这里，自动转为 SRT 字幕。支持两种格式：&#10;1) 带时间轴（LRC）：[00:12.00] 歌词内容&#10;2) 纯文本：每行一句，将按歌曲时长自动均匀分布"
          ></textarea>
          <div class="mt-paste-actions">
            <button type="button" class="mt-btn-sm" :disabled="!a2vLyricsText.trim()" @click="genLyricsSrt">生成 SRT 字幕</button>
            <a v-if="a2vSrtUrl" :href="a2vSrtUrl" :download="srtFileName" class="mt-link">下载 SRT</a>
          </div>
          <pre v-if="a2vGeneratedSrt" class="mt-srt-preview">{{ a2vGeneratedSrt }}</pre>
        </div>
      </div>
      <p v-if="subHasSubtitle" class="mt-hint">字幕将以硬字幕形式烧录到视频中，所有播放器均可显示。</p>

      <button
        class="mt-btn"
        :disabled="!a2vAudio || !a2vImages.length || busy"
        @click="convertA2V"
      >{{ busy && task === 'a2v' ? '合成中…' : '开始合成 MP4' }}</button>

      <div v-if="busy && task === 'a2v'" class="mt-progress">
        <div class="mt-progress-bar" :style="{ width: progress + '%' }"></div>
        <span class="mt-progress-txt">{{ progress }}%</span>
      </div>

      <div v-if="a2vResult" class="mt-result">
        <a :href="a2vResult.url" :download="a2vResult.name" class="mt-download">下载 MP4（{{ fmtSize(a2vResult.size) }}）</a>
      </div>
    </div>

    <p v-if="errMsg" class="mt-err">{{ errMsg }}</p>
    <p v-if="loadingCore" class="mt-loading">首次使用需加载转换引擎（约 30MB），请稍候…</p>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'

const sub = ref('v2a')
const busy = ref(false)
const task = ref('')
const progress = ref(0)
const errMsg = ref('')
const loadingCore = ref(false)

// 上传文件大小上限：30MB
const MAX_SIZE = 30 * 1024 * 1024

// MP4 → MP3 状态
const v2aFile = ref(null)
const v2aResult = ref(null)

// MP3 + 图片 → MP4 状态
const a2vAudio = ref(null)
const a2vAudioDuration = ref(0)
const a2vImages = ref([]) // [{ file, url, height }]
const a2vPerImgSec = ref(4)
const a2vSubMode = ref('upload') // 'upload' | 'paste'
const a2vSubtitle = ref(null)
const a2vLyricsText = ref('')
const a2vGeneratedSrt = ref('')
const a2vSrtUrl = ref('')
const a2vResult = ref(null)

const srtFileName = computed(() => (a2vAudio.value ? (a2vAudio.value.name || 'lyrics').replace(/\.[^.]+$/, '') : 'lyrics') + '.srt')
const subHasSubtitle = computed(() =>
  (a2vSubMode.value === 'upload' && !!a2vSubtitle.value) ||
  (a2vSubMode.value === 'paste' && !!a2vGeneratedSrt.value)
)
const a2vLoopInfo = computed(() => {
  const n = a2vImages.value.length
  if (!n) return ''
  const sec = Number(a2vPerImgSec.value) || 4
  if (!a2vAudioDuration.value) return `共 ${n} 张，每张 ${sec}s；上传音频后自动计算循环次数`
  const loops = Math.max(1, Math.ceil(a2vAudioDuration.value / (n * sec)))
  return `共 ${n} 张 × ${sec}s，将循环约 ${loops} 次铺满歌曲`
})

let ffmpeg = null

function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function checkSize(file, label) {
  if (file.size > MAX_SIZE) {
    errMsg.value = `${label}文件过大（${fmtSize(file.size)}），请控制在 30MB 以内。`
    return false
  }
  return true
}

function onV2aFile(e) {
  const f = e.target.files && e.target.files[0]
  if (f) {
    if (!checkSize(f, '视频')) return
    v2aFile.value = f; v2aResult.value = null; errMsg.value = ''
  }
}
function onA2vAudio(e) {
  const f = e.target.files && e.target.files[0]
  if (f) {
    if (!checkSize(f, '音频')) return
    a2vAudio.value = f
    a2vAudioDuration.value = 0
    a2vResult.value = null
    errMsg.value = ''
    // 探测音频时长，用于自动计算图片循环次数
    const url = URL.createObjectURL(f)
    const au = new Audio()
    au.preload = 'metadata'
    au.onloadedmetadata = () => {
      a2vAudioDuration.value = au.duration || 0
      URL.revokeObjectURL(url)
    }
    au.onerror = () => URL.revokeObjectURL(url)
    au.src = url
  }
}
function onA2vImages(e) {
  const files = e.target.files ? Array.from(e.target.files) : []
  if (!files.length) return
  for (const f of files) {
    if (!checkSize(f, '图片')) continue
    const url = URL.createObjectURL(f)
    const item = { file: f, url, height: 0 }
    a2vImages.value.push(item)
    const img = new Image()
    img.onload = () => { item.height = img.naturalHeight || 0 }
    img.src = url
  }
  a2vResult.value = null
  errMsg.value = ''
}
function removeA2vImage(idx) {
  const item = a2vImages.value[idx]
  if (item && item.url) URL.revokeObjectURL(item.url)
  a2vImages.value.splice(idx, 1)
  a2vResult.value = null
}
function onA2vSubtitle(e) {
  const f = e.target.files && e.target.files[0]
  if (f) {
    if (!checkSize(f, '字幕')) return
    a2vSubtitle.value = f
    a2vResult.value = null
    errMsg.value = ''
  }
}

// ---------- 歌词 → SRT ----------
function srtTime(ms) {
  const total = Math.max(0, Math.round(ms))
  const h = Math.floor(total / 3600000)
  const m = Math.floor((total % 3600000) / 60000)
  const s = Math.floor((total % 60000) / 1000)
  const mill = total % 1000
  const p = (n, w) => String(n).padStart(w, '0')
  return `${p(h, 2)}:${p(m, 2)}:${p(s, 2)},${p(mill, 3)}`
}
function parseLrcToSrt(text) {
  const reTime = /\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]/g
  const items = []
  for (const raw of text.split(/\r?\n/)) {
    reTime.lastIndex = 0
    const stamps = []
    let m
    while ((m = reTime.exec(raw))) {
      const min = parseInt(m[1], 10)
      const sec = parseInt(m[2], 10)
      const frac = m[3] ? ('000' + m[3]).slice(-3) : '000'
      stamps.push((min * 60 + sec) * 1000 + parseInt(frac, 10))
    }
    const content = raw.replace(reTime, '').trim()
    if (!content) continue
    for (const st of stamps) items.push({ start: st, text: content })
  }
  items.sort((a, b) => a.start - b.start)
  if (!items.length) return ''
  let srt = ''
  for (let i = 0; i < items.length; i++) {
    const end = i < items.length - 1 ? items[i + 1].start : items[i].start + 5000
    srt += `${i + 1}\n${srtTime(items[i].start)} --> ${srtTime(end)}\n${items[i].text}\n\n`
  }
  return srt
}
function distributeToSrt(text, totalMs) {
  const lines = text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
  if (!lines.length) return ''
  const slice = totalMs / lines.length
  let srt = ''
  for (let i = 0; i < lines.length; i++) {
    const start = Math.round(i * slice)
    const end = Math.round((i + 1) * slice)
    srt += `${i + 1}\n${srtTime(start)} --> ${srtTime(end)}\n${lines[i]}\n\n`
  }
  return srt
}
function buildLyricsSrt() {
  const text = (a2vLyricsText.value || '').trim()
  if (!text) return ''
  if (/\[\s*\d{1,2}\s*:\s*\d{1,2}/.test(text)) return parseLrcToSrt(text)
  const total = a2vAudioDuration.value
    ? Math.round(a2vAudioDuration.value * 1000)
    : Math.max(60000, text.split(/\r?\n/).filter((x) => x.trim()).length * 5000)
  return distributeToSrt(text, total)
}
function genLyricsSrt() {
  const srt = buildLyricsSrt()
  if (!srt) {
    errMsg.value = '未能从歌词生成字幕，请检查是否包含有效内容（每行一句，或带 [mm:ss] 时间轴）。'
    return
  }
  a2vGeneratedSrt.value = srt
  errMsg.value = ''
  if (a2vSrtUrl.value) URL.revokeObjectURL(a2vSrtUrl.value)
  a2vSrtUrl.value = URL.createObjectURL(new Blob([srt], { type: 'text/plain' }))
}

async function ensureFFmpeg() {
  if (ffmpeg) return ffmpeg
  loadingCore.value = true
  try {
    const { FFmpeg } = await import('@ffmpeg/ffmpeg')
    const { toBlobURL } = await import('@ffmpeg/util')
    ffmpeg = new FFmpeg()
    ffmpeg.on('progress', ({ progress: p }) => {
      const pct = Math.max(0, Math.min(100, Math.round((p || 0) * 100)))
      progress.value = pct
    })
    // 转换引擎 core 文件较大（wasm ~31MB），超出静态托管单文件上限，
    // 改从 CDN 加载（jsdelivr 国内可达且支持 CORS），失败则回退 unpkg。
    const cdns = [
      'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm',
      'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm',
    ]
    let loaded = false
    let lastErr = null
    for (const base of cdns) {
      try {
        const coreURL = await toBlobURL(`${base}/ffmpeg-core.js`, 'text/javascript')
        const wasmURL = await toBlobURL(`${base}/ffmpeg-core.wasm`, 'application/wasm')
        await ffmpeg.load({ coreURL, wasmURL })
        loaded = true
        break
      } catch (e) {
        lastErr = e
      }
    }
    if (!loaded) throw lastErr || new Error('转换引擎加载失败')
  } finally {
    loadingCore.value = false
  }
  return ffmpeg
}

async function readFileBytes(file) {
  const buf = await file.arrayBuffer()
  return new Uint8Array(buf)
}

async function convertV2A() {
  if (!v2aFile.value) return
  errMsg.value = ''
  v2aResult.value = null
  busy.value = true
  task.value = 'v2a'
  progress.value = 0
  try {
    const fm = await ensureFFmpeg()
    const inName = 'input.mp4'
    const outName = 'output.mp3'
    await fm.writeFile(inName, await readFileBytes(v2aFile.value))
    await fm.exec(['-i', inName, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', outName])
    const data = await fm.readFile(outName)
    const blob = new Blob([data.buffer], { type: 'audio/mpeg' })
    const baseName = (v2aFile.value.name || 'audio').replace(/\.[^.]+$/, '')
    v2aResult.value = {
      url: URL.createObjectURL(blob),
      name: `${baseName}.mp3`,
      size: blob.size,
    }
    try { await fm.deleteFile(inName); await fm.deleteFile(outName) } catch (e) {}
    progress.value = 100
  } catch (e) {
    errMsg.value = '转换失败：' + (e && e.message ? e.message : String(e))
  } finally {
    busy.value = false
    task.value = ''
  }
}

async function convertA2V() {
  if (!a2vAudio.value || !a2vImages.value.length) return
  errMsg.value = ''
  a2vResult.value = null
  busy.value = true
  task.value = 'a2v'
  progress.value = 0
  try {
    const fm = await ensureFFmpeg()
    const audName = 'audio.mp3'
    const outName = 'output.mp4'
    await fm.writeFile(audName, await readFileBytes(a2vAudio.value))

    // 写入所有图片
    const n = a2vImages.value.length
    const imgNames = []
    for (let i = 0; i < n; i++) {
      const img = a2vImages.value[i]
      const ext = (img.file.name.match(/\.(jpe?g|png|webp|bmp)$/i) || ['', 'jpg'])[1].toLowerCase()
      const name = `img${i}.${ext === 'jpeg' ? 'jpg' : ext}`
      await fm.writeFile(name, await readFileBytes(img.file))
      imgNames.push(name)
    }

    // 每张图片显示时长 + 根据照片数量与歌曲时长计算循环次数
    const sec = Math.max(1, Number(a2vPerImgSec.value) || 4)
    const dur = a2vAudioDuration.value || 0
    const cycle = n * sec
    const loops = dur > 0 ? Math.max(1, Math.ceil(dur / cycle)) : Math.max(1, Math.ceil(180 / cycle))
    const list = []
    for (let l = 0; l < loops; l++) {
      for (let i = 0; i < n; i++) {
        list.push(`file '${imgNames[i]}'`)
        list.push(`duration ${sec}`)
      }
    }
    await fm.writeFile('list.txt', new TextEncoder().encode(list.join('\n') + '\n'))

    // 基础视频滤镜：尺寸取偶 + yuv420p 兼容
    const firstH = a2vImages.value[0].height || 720
    let vf = 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p'

    // 字幕（可选）：烧录为硬字幕
    let subName = null
    if (a2vSubMode.value === 'upload' && a2vSubtitle.value) {
      const subExt = (a2vSubtitle.value.name.match(/\.(srt|vtt|ass|ssa)$/i) || ['', 'srt'])[1].toLowerCase()
      subName = `sub.${subExt}`
      await fm.writeFile(subName, await readFileBytes(a2vSubtitle.value))
    } else if (a2vSubMode.value === 'paste') {
      let srt = buildLyricsSrt()
      if (srt) {
        a2vGeneratedSrt.value = srt
        if (a2vSrtUrl.value) URL.revokeObjectURL(a2vSrtUrl.value)
        a2vSrtUrl.value = URL.createObjectURL(new Blob([srt], { type: 'text/plain' }))
        subName = 'sub.srt'
        await fm.writeFile(subName, new TextEncoder().encode(srt))
      }
    }
    if (subName) {
      const fontSize = Math.round(Math.max(18, firstH / 24))
      vf += `,subtitles=${subName}:force_style='FontSize=${fontSize},Alignment=2,MarginV=40,Outline=2,OutlineColour=&H000000'`
    }

    const args = [
      '-f', 'concat', '-safe', '0',
      '-i', 'list.txt',
      '-i', audName,
      '-map', '0:v:0', '-map', '1:a:0',
      '-c:v', 'libx264',
      '-preset', 'ultrafast',
      '-tune', 'stillimage',
      '-vf', vf,
      '-c:a', 'aac',
      '-b:a', '192k',
      '-shortest',
      '-movflags', '+faststart',
      outName,
    ]

    await fm.exec(args)
    const data = await fm.readFile(outName)
    const blob = new Blob([data.buffer], { type: 'video/mp4' })
    const baseName = (a2vAudio.value.name || 'video').replace(/\.[^.]+$/, '')
    a2vResult.value = {
      url: URL.createObjectURL(blob),
      name: `${baseName}.mp4`,
      size: blob.size,
    }
    try {
      await fm.deleteFile('list.txt')
      for (const name of imgNames) await fm.deleteFile(name)
      await fm.deleteFile(audName)
      if (subName) await fm.deleteFile(subName)
      await fm.deleteFile(outName)
    } catch (e) {}
    progress.value = 100
  } catch (e) {
    errMsg.value = '合成失败：' + (e && e.message ? e.message : String(e))
  } finally {
    busy.value = false
    task.value = ''
  }
}

onUnmounted(() => {
  for (const img of a2vImages.value) {
    if (img.url) URL.revokeObjectURL(img.url)
  }
  if (a2vSrtUrl.value) URL.revokeObjectURL(a2vSrtUrl.value)
  if (v2aResult.value) URL.revokeObjectURL(v2aResult.value.url)
  if (a2vResult.value) URL.revokeObjectURL(a2vResult.value.url)
})
</script>

<style scoped>
.media-tools { padding: 4px 0; }
.mt-subtabs { display: flex; gap: 0; border: 1px solid #b1b4b6; margin-bottom: 14px; }
.mt-subtab {
  flex: 1; text-align: center; padding: 10px 8px; cursor: pointer;
  font-size: 15px; color: #1d70b8; background: #fff; border-right: 1px solid #b1b4b6;
  user-select: none;
}
.mt-subtab:last-child { border-right: none; }
.mt-subtab.active { background: #1d70b8; color: #fff; font-weight: 600; }
.mt-note { font-size: 13px; color: #505a5f; margin: 0 0 14px; line-height: 1.5; }
.mt-card { border: 1px solid #b1b4b6; padding: 16px; background: #fff; }
.mt-card-title { font-size: 16px; font-weight: 600; color: #0b0c0c; margin-bottom: 14px; }
.mt-drop {
  display: block; border: 2px dashed #b1b4b6; padding: 18px 12px; text-align: center;
  color: #505a5f; font-size: 14px; cursor: pointer; margin-bottom: 12px; background: #f8f8f8;
}
.mt-drop.filled { border-color: #1d70b8; color: #0b0c0c; background: #eef6fc; }
.mt-sub-drop { border-style: dotted; background: #fbfbfb; }
.mt-hint { font-size: 12px; color: #505a5f; margin: -6px 0 12px; }
.mt-preview { display: block; max-width: 100%; max-height: 160px; margin: 0 auto 12px; border: 1px solid #b1b4b6; }
.mt-btn {
  width: 100%; padding: 12px; font-size: 15px; font-weight: 600; color: #fff;
  background: #00703c; border: none; cursor: pointer;
}
.mt-btn:disabled { background: #b1b4b6; cursor: not-allowed; }
.mt-progress { position: relative; height: 22px; background: #e8e8e8; margin-top: 12px; border: 1px solid #b1b4b6; }
.mt-progress-bar { height: 100%; background: #1d70b8; transition: width .2s; }
.mt-progress-txt {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  line-height: 22px; font-size: 12px; color: #0b0c0c;
}
.mt-result { margin-top: 14px; }
.mt-download {
  display: block; text-align: center; padding: 12px; background: #1d70b8; color: #fff;
  text-decoration: none; font-size: 15px; font-weight: 600;
}
.mt-err { color: #d4351c; font-size: 14px; margin-top: 12px; }
.mt-loading { color: #b95900; font-size: 13px; margin-top: 10px; }

/* 多图缩略图 */
.mt-thumbs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.mt-thumb {
  position: relative; width: 84px; height: 84px; border: 1px solid #b1b4b6;
  background: #f3f3f3; overflow: hidden;
}
.mt-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.mt-thumb-idx {
  position: absolute; left: 0; top: 0; background: #1d70b8; color: #fff;
  font-size: 12px; line-height: 18px; padding: 0 6px;
}
.mt-thumb-del {
  position: absolute; right: 0; top: 0; width: 22px; height: 22px; border: none;
  background: rgba(212,53,28,.92); color: #fff; font-size: 16px; line-height: 22px;
  cursor: pointer; padding: 0;
}

/* 每张图片时长 */
.mt-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.mt-inline-label { font-size: 14px; color: #0b0c0c; }
.mt-num {
  width: 64px; padding: 6px 8px; border: 1px solid #b1b4b6; font-size: 14px;
}
.mt-hint-inline { font-size: 12px; color: #505a5f; }

/* 字幕来源切换 */
.mt-sub-block { margin-bottom: 12px; }
.mt-sub-modes { display: flex; gap: 18px; margin-bottom: 10px; font-size: 14px; color: #0b0c0c; }
.mt-radio { cursor: pointer; user-select: none; }
.mt-paste-block { border: 1px solid #b1b4b6; padding: 10px; background: #fbfbfb; }
.mt-textarea {
  width: 100%; min-height: 120px; box-sizing: border-box; border: 1px solid #b1b4b6;
  padding: 8px; font-size: 13px; line-height: 1.5; resize: vertical; font-family: inherit;
}
.mt-paste-actions { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.mt-btn-sm {
  padding: 7px 14px; font-size: 13px; font-weight: 600; color: #fff; background: #1d70b8;
  border: none; cursor: pointer;
}
.mt-btn-sm:disabled { background: #b1b4b6; cursor: not-allowed; }
.mt-link { font-size: 13px; color: #1d70b8; text-decoration: underline; }
.mt-srt-preview {
  margin: 10px 0 0; max-height: 200px; overflow: auto; background: #fff; border: 1px solid #b1b4b6;
  padding: 8px; font-size: 12px; line-height: 1.4; white-space: pre-wrap; word-break: break-all;
}
</style>
