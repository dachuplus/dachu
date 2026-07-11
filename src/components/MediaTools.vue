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
        <span v-else>音频：{{ a2vAudio.name }}（{{ fmtSize(a2vAudio.size) }}）</span>
      </label>

      <label class="mt-drop" :class="{ filled: a2vImage }">
        <input type="file" accept="image/*" @change="onA2vImage" hidden />
        <span v-if="!a2vImage">点击选择封面图片（JPG / PNG）</span>
        <span v-else>图片：{{ a2vImage.name }}（{{ fmtSize(a2vImage.size) }}）</span>
      </label>

      <img v-if="a2vPreview" :src="a2vPreview" class="mt-preview" alt="封面预览" />

      <label class="mt-drop mt-sub-drop" :class="{ filled: a2vSubtitle }">
        <input type="file" accept=".srt,.vtt,.ass,.ssa,text/plain" @change="onA2vSubtitle" hidden />
        <span v-if="!a2vSubtitle">（可选）点击上传字幕文件（SRT / VTT / ASS / SSA）</span>
        <span v-else>字幕：{{ a2vSubtitle.name }}（{{ fmtSize(a2vSubtitle.size) }}）</span>
      </label>
      <p v-if="a2vSubtitle" class="mt-hint">字幕将以硬字幕形式烧录到视频中，所有播放器均可显示。</p>

      <button
        class="mt-btn"
        :disabled="!a2vAudio || !a2vImage || busy"
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
import { ref, onUnmounted } from 'vue'

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
const a2vImage = ref(null)
const a2vSubtitle = ref(null)
const a2vPreview = ref('')
const a2vImgH = ref(0)
const a2vResult = ref(null)

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
    a2vAudio.value = f; a2vResult.value = null; errMsg.value = ''
  }
}
function onA2vImage(e) {
  const f = e.target.files && e.target.files[0]
  if (f) {
    if (!checkSize(f, '图片')) return
    a2vImage.value = f
    a2vResult.value = null
    errMsg.value = ''
    if (a2vPreview.value) URL.revokeObjectURL(a2vPreview.value)
    const url = URL.createObjectURL(f)
    a2vPreview.value = url
    const img = new Image()
    img.onload = () => { a2vImgH.value = img.naturalHeight || 0 }
    img.src = url
  }
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
  if (!a2vAudio.value || !a2vImage.value) return
  errMsg.value = ''
  a2vResult.value = null
  busy.value = true
  task.value = 'a2v'
  progress.value = 0
  try {
    const fm = await ensureFFmpeg()
    const imgExt = (a2vImage.value.name.match(/\.(jpe?g|png|webp|bmp)$/i) || ['', 'jpg'])[1].toLowerCase()
    const imgName = `cover.${imgExt === 'jpeg' ? 'jpg' : imgExt}`
    const audName = 'audio.mp3'
    const outName = 'output.mp4'
    await fm.writeFile(imgName, await readFileBytes(a2vImage.value))
    await fm.writeFile(audName, await readFileBytes(a2vAudio.value))

    // 基础视频滤镜：尺寸取偶 + yuv420p 兼容
    let vf = 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p'

    // 字幕（可选）：烧录为硬字幕，字体大小按封面高度自适应，带黑色描边保证可读性
    let subName = null
    if (a2vSubtitle.value) {
      const subExt = (a2vSubtitle.value.name.match(/\.(srt|vtt|ass|ssa)$/i) || ['', 'srt'])[1].toLowerCase()
      subName = `sub.${subExt}`
      await fm.writeFile(subName, await readFileBytes(a2vSubtitle.value))
      const fontSize = Math.round(Math.max(18, (a2vImgH.value || 720) / 24))
      vf += `,subtitles=${subName}:force_style='FontSize=${fontSize},Alignment=2,MarginV=40,Outline=2,OutlineColour=&H000000'`
    }

    const args = [
      '-loop', '1',
      '-framerate', '2',
      '-i', imgName,
      '-i', audName,
    ]
    if (subName) args.push('-i', subName)
    args.push(
      '-c:v', 'libx264',
      '-preset', 'ultrafast',
      '-tune', 'stillimage',
      '-vf', vf,
      '-c:a', 'aac',
      '-b:a', '192k',
      '-shortest',
      '-movflags', '+faststart',
      outName,
    )

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
      await fm.deleteFile(imgName)
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
  if (a2vPreview.value) URL.revokeObjectURL(a2vPreview.value)
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
</style>
