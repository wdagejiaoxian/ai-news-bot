/**
 * Element Plus 组件按需引入
 * 仅注册项目实际使用的组件，减少打包体积
 *
 * 使用方式：在 main.ts 中 import 后调用 setupElementPlus(app)
 */

import type { App } from 'vue'

// 布局
import { ElContainer, ElRow, ElCol } from 'element-plus'

// 导航
import { ElBreadcrumb, ElBreadcrumbItem } from 'element-plus'
import { ElDropdown, ElDropdownMenu, ElDropdownItem } from 'element-plus'
import { ElPagination } from 'element-plus'

// 展示
import { ElCard } from 'element-plus'
import { ElTable, ElTableColumn } from 'element-plus'
import { ElTag } from 'element-plus'
import { ElAlert } from 'element-plus'
import { ElResult } from 'element-plus'
import { ElDescriptions, ElDescriptionsItem } from 'element-plus'
import { ElDivider } from 'element-plus'
import { ElAvatar } from 'element-plus'
import { ElIcon } from 'element-plus'
import { ElLink } from 'element-plus'
import { ElSkeleton, ElSkeletonItem } from 'element-plus'

// 表单
import { ElForm, ElFormItem } from 'element-plus'
import { ElInput } from 'element-plus'
import { ElInputNumber } from 'element-plus'
import { ElSelect, ElOption } from 'element-plus'
import { ElSwitch } from 'element-plus'
import { ElSlider } from 'element-plus'
import { ElRadioGroup, ElRadioButton } from 'element-plus'
import { ElTimePicker } from 'element-plus'

// 反馈
import { ElButton } from 'element-plus'
import { ElPopconfirm } from 'element-plus'
import { ElDialog } from 'element-plus'

const components = [
  // 布局
  ElContainer,
  ElRow,
  ElCol,
  // 导航
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElPagination,
  // 展示
  ElCard,
  ElTable,
  ElTableColumn,
  ElTag,
  ElAlert,
  ElResult,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElAvatar,
  ElIcon,
  ElLink,
  ElSkeleton,
  ElSkeletonItem,
  // 表单
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElSwitch,
  ElSlider,
  ElRadioGroup,
  ElRadioButton,
  ElTimePicker,
  // 反馈
  ElButton,
  ElPopconfirm,
  ElDialog,
]

export function setupElementPlus(app: App) {
  components.forEach((component) => {
    app.component(component.name!, component)
  })
}

export default setupElementPlus
