/**
 * 表单验证工具 composable
 *
 * 功能：
 * - 验证失败时聚焦到第一个错误字段
 * - 表单验证辅助函数
 */
import type { FormInstance } from 'element-plus'

/**
 * 聚焦到第一个验证失败的字段
 */
export function focusFirstErrorField(formEl: HTMLElement): void {
  // 找到第一个有错误状态的表单项
  const firstErrorItem = formEl.querySelector('.el-form-item.is-error')
  if (firstErrorItem) {
    // 找到表单项内的输入框并聚焦
    const input = firstErrorItem.querySelector('.el-input__wrapper, .el-textarea__inner, input, textarea')
    if (input instanceof HTMLElement) {
      input.focus()
    }
  }
}

/**
 * 表单验证失败后聚焦到错误字段的处理器
 */
export async function validateAndFocusOnError(
  formRef: FormInstance | undefined,
  formEl: HTMLElement | undefined,
  onSuccess?: () => void
): Promise<boolean> {
  if (!formRef) return false

  try {
    const valid = await formRef.validate()
    if (valid && onSuccess) {
      onSuccess()
    }
    return valid ?? false
  } catch {
    // 验证失败，聚焦到第一个错误字段
    if (formEl) {
      // 延迟一下确保 DOM 已更新
      setTimeout(() => {
        focusFirstErrorField(formEl)
      }, 100)
    }
    return false
  }
}
