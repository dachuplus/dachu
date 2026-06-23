<template>
  <Teleport to="body">
    <div v-if="confirmState.show" class="confirm-overlay" @click.self="confirmCancel()">
      <div class="confirm-dialog" role="dialog" aria-modal="true">
        <h2 class="confirm-dialog__title">{{ confirmState.title }}</h2>
        <p class="confirm-dialog__message">{{ confirmState.message }}</p>
        <div class="confirm-dialog__actions">
          <button class="govuk-button govuk-button--secondary" @click="confirmCancel()">
            取消
          </button>
          <button class="govuk-button" @click="confirmAccept()">
            确定
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast, confirmAccept, confirmCancel } from '../composables/useToast.js'

const { confirmState } = useToast()
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(11, 12, 12, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.confirm-dialog {
  background: #ffffff;
  border: 1px solid #b1b4b6;
  padding: 30px;
  max-width: 440px;
  width: 100%;
}

.confirm-dialog__title {
  font-size: 24px;
  font-weight: 700;
  color: #0b0c0c;
  margin: 0 0 15px;
  line-height: 1.25;
}

.confirm-dialog__message {
  font-size: 19px;
  color: #0b0c0c;
  margin: 0 0 30px;
  line-height: 1.35;
}

.confirm-dialog__actions {
  display: flex;
  gap: 15px;
  justify-content: flex-end;
}

.govuk-button {
  display: inline-block;
  padding: 8px 10px;
  border: none;
  font-size: 19px;
  line-height: 1.25;
  font-family: inherit;
  cursor: pointer;
  color: #ffffff;
  background: #00703c;
  box-shadow: 0 2px 0 #002d18;
}

.govuk-button:hover {
  background: #005a30;
}

.govuk-button:active {
  top: 2px;
  box-shadow: none;
}

.govuk-button--secondary {
  background: #f3f2f1;
  color: #0b0c0c;
  box-shadow: 0 2px 0 #929191;
}

.govuk-button--secondary:hover {
  background: #dbdad9;
}

@media (max-width: 768px) {
  .confirm-dialog {
    padding: 20px;
  }
  .confirm-dialog__title {
    font-size: 20px;
  }
  .confirm-dialog__message {
    font-size: 16px;
  }
}
</style>
