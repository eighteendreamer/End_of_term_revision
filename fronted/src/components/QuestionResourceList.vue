<template>
  <!-- 资源为空时整块不出现，避免题面上多一个空折叠头 -->
  <n-collapse v-if="items.length" :default-expanded-names="[]" class="resource-block">
    <n-collapse-item :title="`公式与图形资源（${items.length}）`" name="resources">
      <n-space vertical :size="8">
        <div v-for="(item, index) in items" :key="index" class="resource-item">
          <n-tag size="small" :bordered="false">{{ label(item.type) }}</n-tag>
          <TableRenderer v-if="item.type === 'table_json'" :content="item.content" />
          <!-- 图片地址来自模型输出，按纯文本展示，不生成可点击链接 -->
          <n-text v-else-if="item.type === 'image'" depth="3" code>{{ item.content }}</n-text>
          <FormulaRenderer v-else :content="item.content" />
        </div>
      </n-space>
    </n-collapse-item>
  </n-collapse>
</template>

<script setup>
import { computed } from 'vue'
import FormulaRenderer from './FormulaRenderer.vue'
import TableRenderer from './TableRenderer.vue'

const props = defineProps({
  // 统一形状 [{ type, content }]；question_resources 表的字段名在调用处归一
  resources: {
    type: Array,
    default: () => []
  }
})

const LABELS = {
  image: '图片',
  table_json: '表格',
  diagram_desc: '图形描述',
  latex: '公式',
  other: '其他'
}

const items = computed(() =>
  (props.resources || []).filter((item) => item && item.content)
)

const label = (type) => LABELS[type] || type || '其他'
</script>

<style scoped>
.resource-block {
  margin-top: 8px;
}

.resource-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.resource-item > :nth-child(2) {
  flex: 1;
  min-width: 0;
}
</style>
