<template>
  <div class="ms-game">
    <div class="ms-hud">
      <div class="ms-stat">剩余地雷：{{ remainingMines }}</div>
      <button class="ms-new-btn" @click="newGame">新游戏</button>
      <div class="ms-stat">时间：{{ time }}</div>
    </div>
    <div class="ms-board" @contextmenu.prevent>
      <div
        v-for="(cell, idx) in board"
        :key="idx"
        class="ms-cell"
        :class="{
          revealed: cell.revealed,
          flagged: cell.flagged,
          mine: cell.revealed && cell.mine,
          safe: cell.revealed && !cell.mine,
          highlight: cell.adjacent > 0 && cell.revealed,
        }"
        @click="onClick(cell)"
        @contextmenu.prevent="onRightClick(cell)"
      >
        <template v-if="cell.flagged">旗</template>
        <template v-else-if="cell.revealed && cell.mine">雷</template>
        <template v-else-if="cell.revealed && cell.adjacent > 0">{{ cell.adjacent }}</template>
      </div>
    </div>
    <p v-if="statusText" class="ms-status">{{ statusText }}</p>
    <p class="ms-hint">左键翻开，右键插旗。首次点击保证安全。</p>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'

const ROWS = 9
const COLS = 9
const MINES = 10

const board = ref([])
const started = ref(false)
const over = ref(false)
const won = ref(false)
const time = ref(0)
const timer = ref(null)

const remainingMines = computed(() => {
  const flags = board.value.filter((c) => c.flagged).length
  return MINES - flags
})

const statusText = computed(() => {
  if (over.value && won.value) return '恭喜，你排完了所有地雷！'
  if (over.value && !won.value) return '游戏结束，踩到地雷了。'
  return ''
})

function makeCell(r, c) {
  return { r, c, mine: false, revealed: false, flagged: false, adjacent: 0 }
}

function newGame() {
  clearInterval(timer.value)
  timer.value = null
  started.value = false
  over.value = false
  won.value = false
  time.value = 0
  const arr = []
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      arr.push(makeCell(r, c))
    }
  }
  board.value = arr
}

function get(r, c) {
  if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return null
  return board.value[r * COLS + c]
}

function neighbors(cell) {
  const res = []
  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      if (dr === 0 && dc === 0) continue
      const n = get(cell.r + dr, cell.c + dc)
      if (n) res.push(n)
    }
  }
  return res
}

function placeMines(safeCell) {
  const safeSet = new Set([`${safeCell.r},${safeCell.c}`])
  // 也保护 safeCell 周围一圈，确保首点大开
  neighbors(safeCell).forEach((n) => safeSet.add(`${n.r},${n.c}`))

  let placed = 0
  while (placed < MINES) {
    const idx = Math.floor(Math.random() * board.value.length)
    const cell = board.value[idx]
    if (cell.mine || safeSet.has(`${cell.r},${cell.c}`)) continue
    cell.mine = true
    placed++
  }

  board.value.forEach((cell) => {
    if (cell.mine) return
    cell.adjacent = neighbors(cell).filter((n) => n.mine).length
  })
}

function reveal(cell) {
  if (cell.revealed || cell.flagged || over.value) return
  cell.revealed = true
  if (cell.adjacent === 0 && !cell.mine) {
    neighbors(cell).forEach((n) => reveal(n))
  }
}

function checkWin() {
  const allRevealed = board.value.every((c) => c.mine || c.revealed)
  if (allRevealed) {
    over.value = true
    won.value = true
    clearInterval(timer.value)
  }
}

function onClick(cell) {
  if (over.value || cell.flagged) return
  if (!started.value) {
    started.value = true
    placeMines(cell)
    timer.value = setInterval(() => time.value++, 1000)
  }
  if (cell.mine) {
    cell.revealed = true
    over.value = true
    won.value = false
    clearInterval(timer.value)
    board.value.filter((c) => c.mine).forEach((c) => (c.revealed = true))
    return
  }
  reveal(cell)
  checkWin()
}

function onRightClick(cell) {
  if (over.value || cell.revealed) return
  cell.flagged = !cell.flagged
}

onUnmounted(() => clearInterval(timer.value))

newGame()
</script>

<style scoped>
.ms-game {
  user-select: none;
}
.ms-hud {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}
.ms-stat {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.ms-new-btn {
  background: #1d70b8;
  color: #fff;
  border: none;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.ms-new-btn:hover { background: #003078; }
.ms-board {
  display: grid;
  grid-template-columns: repeat(9, 28px);
  grid-template-rows: repeat(9, 28px);
  gap: 1px;
  background: #b1b4b6;
  border: 1px solid #b1b4b6;
  width: fit-content;
}
.ms-cell {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  background: #f3f2f1;
}
.ms-cell:not(.revealed):hover { background: #e5e4e2; }
.ms-cell.revealed.safe { background: #fff; color: #0b0c0c; }
.ms-cell.revealed.mine { background: #d4351c; color: #fff; }
.ms-cell.highlight { color: #1d70b8; }
.ms-cell.flagged { background: #ffdd00; }
.ms-status {
  margin: 12px 0 0;
  font-size: 15px;
  font-weight: 700;
  color: #00703c;
}
.ms-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
