<template>
  <div class="games-panel">
    <div class="games-subtabs">
      <div
        class="games-subtab"
        :class="{ active: activeGame === 'minesweeper' }"
        @click="activeGame = 'minesweeper'"
      >扫雷</div>
      <div
        class="games-subtab"
        :class="{ active: activeGame === '2048' }"
        @click="activeGame = '2048'"
      >2048</div>
    </div>

    <div class="games-area">
      <MinesweeperGame v-if="activeGame === 'minesweeper'" />
      <Game2048 v-else />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MinesweeperGame from './MinesweeperGame.vue'
import Game2048 from './Game2048.vue'

const activeGame = ref('minesweeper')
</script>

<style scoped>
.games-panel { padding: 4px 0; }
.games-subtabs {
  display: flex;
  gap: 0;
  border: 1px solid #b1b4b6;
  margin-bottom: 14px;
}
.games-subtab {
  flex: 1;
  text-align: center;
  padding: 10px 8px;
  cursor: pointer;
  font-size: 15px;
  color: #1d70b8;
  background: #fff;
  border-right: 1px solid #b1b4b6;
  user-select: none;
}
.games-subtab:last-child { border-right: none; }
.games-subtab.active { background: #1d70b8; color: #fff; font-weight: 700; }
.games-area {
  display: flex;
  justify-content: center;
}
</style>
