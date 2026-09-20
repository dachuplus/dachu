<template>
  <div class="g2048-game" ref="rootRef" tabindex="0" @keydown.prevent="onKeydown">
    <div class="g2048-hud">
      <div class="g2048-scores">
        <span>得分：{{ score }}</span>
        <span>最佳：{{ bestScore }}</span>
      </div>
      <button class="g2048-new-btn" @click="newGame">新游戏</button>
    </div>

    <div class="g2048-board" @touchstart="onTouchStart" @touchend="onTouchEnd">
      <div class="g2048-grid">
        <div v-for="n in 16" :key="n" class="g2048-cell g2048-cell--empty"></div>
      </div>
      <div class="g2048-tiles">
        <div
          v-for="tile in tiles"
          :key="tile.id"
          class="g2048-tile"
          :class="'g2048-tile--' + tile.value"
          :style="tileStyle(tile)"
        >{{ tile.value }}</div>
      </div>
    </div>

    <p v-if="won && !keepPlaying" class="g2048-status g2048-status--win">你合成 2048 了！</p>
    <p v-else-if="won && keepPlaying" class="g2048-status g2048-status--win">已达成 2048，继续挑战更高分！</p>
    <p v-else-if="gameOver" class="g2048-status g2048-status--lose">没有可移动的格子了。</p>
    <p class="g2048-hint">使用方向键或滑动屏幕移动方块。相同数字碰撞会合并。</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const SIZE = 4
const BEST_KEY = 'dachu_2048_best'

const board = ref([])
const score = ref(0)
const bestScore = ref(0)
const won = ref(false)
const gameOver = ref(false)
const keepPlaying = ref(false)
const rootRef = ref(null)
let nextId = 1

const tiles = computed(() => {
  const list = []
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      const v = board.value[r][c]
      if (v) list.push({ id: v.id, value: v.value, r, c })
    }
  }
  return list
})

function loadBest() {
  try {
    bestScore.value = Math.max(0, parseInt(localStorage.getItem(BEST_KEY) || '0', 10) || 0)
  } catch (e) { bestScore.value = 0 }
}

function saveBest() {
  try { localStorage.setItem(BEST_KEY, String(bestScore.value)) } catch (e) {}
}

function newGame() {
  score.value = 0
  won.value = false
  gameOver.value = false
  keepPlaying.value = false
  board.value = Array.from({ length: SIZE }, () => Array(SIZE).fill(null))
  addRandomTile()
  addRandomTile()
  if (rootRef.value) rootRef.value.focus()
}

function emptyCells() {
  const res = []
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (!board.value[r][c]) res.push({ r, c })
    }
  }
  return res
}

function addRandomTile() {
  const empties = emptyCells()
  if (!empties.length) return
  const { r, c } = empties[Math.floor(Math.random() * empties.length)]
  board.value[r][c] = { id: nextId++, value: Math.random() < 0.9 ? 2 : 4 }
}

function tileStyle(tile) {
  const size = 64
  const gap = 8
  return {
    transform: `translate(${tile.c * (size + gap)}px, ${tile.r * (size + gap)}px)`,
  }
}

function slideRow(row) {
  let arr = row.filter(Boolean)
  let merged = false
  for (let i = 0; i < arr.length - 1; i++) {
    if (arr[i].value === arr[i + 1].value) {
      arr[i].value *= 2
      arr[i].id = nextId++
      score.value += arr[i].value
      if (arr[i].value === 2048 && !won.value) won.value = true
      arr[i + 1] = null
      merged = true
    }
  }
  arr = arr.filter(Boolean)
  while (arr.length < SIZE) arr.push(null)
  return arr
}

function moveLeft() {
  let moved = false
  for (let r = 0; r < SIZE; r++) {
    const before = board.value[r].map((x) => (x ? x.value : 0)).join(',')
    board.value[r] = slideRow(board.value[r])
    const after = board.value[r].map((x) => (x ? x.value : 0)).join(',')
    if (before !== after) moved = true
  }
  return moved
}

function rotateCW(matrix) {
  const n = matrix.length
  const res = Array.from({ length: n }, () => Array(n).fill(null))
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      res[c][n - 1 - r] = matrix[r][c]
    }
  }
  return res
}

function move(dir) {
  // dir: 0=left, 1=up, 2=right, 3=down
  let rotated = board.value
  for (let i = 0; i < dir; i++) rotated = rotateCW(rotated)
  let moved = false
  const before = JSON.stringify(rotated.map((row) => row.map((x) => (x ? x.value : 0))))
  for (let r = 0; r < SIZE; r++) rotated[r] = slideRow(rotated[r])
  const after = JSON.stringify(rotated.map((row) => row.map((x) => (x ? x.value : 0))))
  if (before !== after) moved = true
  for (let i = 0; i < (4 - dir) % 4; i++) rotated = rotateCW(rotated)
  board.value = rotated
  if (moved) {
    addRandomTile()
    if (score.value > bestScore.value) {
      bestScore.value = score.value
      saveBest()
    }
    if (!hasMoves()) gameOver.value = true
  }
}

function hasMoves() {
  if (emptyCells().length) return true
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      const v = board.value[r][c].value
      if (c < SIZE - 1 && board.value[r][c + 1].value === v) return true
      if (r < SIZE - 1 && board.value[r + 1][c].value === v) return true
    }
  }
  return false
}

function onKeydown(e) {
  if (gameOver.value) return
  switch (e.key) {
    case 'ArrowLeft': move(0); break
    case 'ArrowUp': move(1); break
    case 'ArrowRight': move(2); break
    case 'ArrowDown': move(3); break
  }
  if (won.value && !keepPlaying.value) keepPlaying.value = true
}

let touchStart = null
function onTouchStart(e) {
  if (gameOver.value) return
  const t = e.touches[0]
  touchStart = { x: t.clientX, y: t.clientY }
}
function onTouchEnd(e) {
  if (!touchStart || gameOver.value) return
  const t = e.changedTouches[0]
  const dx = t.clientX - touchStart.x
  const dy = t.clientY - touchStart.y
  const absX = Math.abs(dx)
  const absY = Math.abs(dy)
  if (Math.max(absX, absY) < 24) return
  if (absX > absY) {
    move(dx > 0 ? 2 : 0)
  } else {
    move(dy > 0 ? 3 : 1)
  }
  if (won.value && !keepPlaying.value) keepPlaying.value = true
  touchStart = null
}

onMounted(() => {
  loadBest()
  newGame()
})
</script>

<style scoped>
.g2048-game {
  user-select: none;
  outline: none;
}
.g2048-hud {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}
.g2048-scores {
  display: flex;
  gap: 16px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.g2048-new-btn {
  background: #1d70b8;
  color: #fff;
  border: none;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.g2048-new-btn:hover { background: #003078; }
.g2048-board {
  position: relative;
  width: 280px;
  height: 280px;
  background: #b1b4b6;
  padding: 8px;
}
.g2048-grid {
  position: absolute;
  inset: 8px;
  display: grid;
  grid-template-columns: repeat(4, 64px);
  grid-template-rows: repeat(4, 64px);
  gap: 8px;
}
.g2048-cell { width: 64px; height: 64px; }
.g2048-cell--empty { background: #f3f2f1; }
.g2048-tiles {
  position: absolute;
  inset: 8px;
  pointer-events: none;
}
.g2048-tile {
  position: absolute;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  transition: transform 0.12s ease;
}
.g2048-tile--2    { background: #1d70b8; }
.g2048-tile--4    { background: #003078; }
.g2048-tile--8    { background: #00703c; }
.g2048-tile--16   { background: #4c2c92; }
.g2048-tile--32   { background: #d4351c; }
.g2048-tile--64   { background: #b58800; }
.g2048-tile--128  { background: #5694ca; }
.g2048-tile--256  { background: #28a197; }
.g2048-tile--512  { background: #f47738; }
.g2048-tile--1024 { background: #6f72af; font-size: 18px; }
.g2048-tile--2048 { background: #00703c; font-size: 18px; }
.g2048-tile--4096,
.g2048-tile--8192,
.g2048-tile--16384,
.g2048-tile--32768,
.g2048-tile--65536 { background: #0b0c0c; font-size: 14px; }
.g2048-status {
  margin: 12px 0 0;
  font-size: 15px;
  font-weight: 700;
}
.g2048-status--win { color: #00703c; }
.g2048-status--lose { color: #d4351c; }
.g2048-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
