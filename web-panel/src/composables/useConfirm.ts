/**
 * 操作确认 Composable - 统一操作确认反馈
 *
 * 功能：
 * - 统一的删除确认
 * - 统一的危险操作确认
 * - 自定义确认消息和按钮文字
 * - 支持异步确认操作
 *
 * @example
 * const { confirmDelete, confirmDangerous } = useConfirm()
 *
 * // 删除确认
 * const confirmed = await confirmDelete('文章标题')
 *
 * // 危险操作确认
 * const confirmed = await confirmDangerous('清空所有数据', '此操作不可恢复')
 */
import { ElMessageBox, type ElMessageBoxOptions } from 'element-plus'

/**
 * 确认选项
 */
export interface ConfirmOptions {
  /** 确认标题 */
  title?: string
  /** 确认消息 */
  message?: string
  /** 确认按钮文字 */
  confirmText?: string
  /** 取消按钮文字 */
  cancelText?: string
  /** 按钮类型 */
  type?: 'warning' | 'danger' | 'info' | 'success'
  /** 是否显示取消按钮 */
  showCancel?: boolean
}

/**
 * 确认结果
 */
export interface ConfirmResult {
  /** 是否确认 */
  confirmed: boolean
  /** 是否取消 */
  cancelled: boolean
  /** 确认时间戳 */
  timestamp: number
}

/**
 * useConfirm 组合式函数
 */
export function useConfirm() {
  /**
   * 删除确认
   * @param name - 要删除的资源名称
   * @param options - 额外选项
   */
  async function confirmDelete(
    name?: string,
    options: ConfirmOptions = {}
  ): Promise<boolean> {
    const {
      title = '删除确认',
      message = name ? `确定要删除「${name}」吗？此操作不可撤销。` : '确定要删除吗？此操作不可撤销。',
      confirmText = '删除',
      cancelText = '取消',
      type = 'warning',
    } = options

    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type,
        confirmButtonClass: 'el-button--danger',
      } as ElMessageBoxOptions)
      return true
    } catch {
      return false
    }
  }

  /**
   * 危险操作确认
   * @param action - 操作名称
   * @param description - 操作描述
   * @param options - 额外选项
   */
  async function confirmDangerous(
    action: string,
    description?: string,
    options: ConfirmOptions = {}
  ): Promise<boolean> {
    const {
      title = '危险操作确认',
      message = description || `确定要执行「${action}」吗？此操作可能造成不可逆的后果。`,
      confirmText = '确认执行',
      cancelText = '取消',
      type = 'danger',
    } = options

    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type,
        confirmButtonClass: 'el-button--danger',
      } as ElMessageBoxOptions)
      return true
    } catch {
      return false
    }
  }

  /**
   * 一般确认
   * @param message - 确认消息
   * @param options - 额外选项
   */
  async function confirm(
    message: string,
    options: ConfirmOptions = {}
  ): Promise<boolean> {
    const {
      title = '操作确认',
      confirmText = '确定',
      cancelText = '取消',
      type = 'info',
    } = options

    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type,
      } as ElMessageBoxOptions)
      return true
    } catch {
      return false
    }
  }

  /**
   * 带输入的确认（如输入"DELETE"确认）
   * @param message - 提示消息
   * @param inputPlaceholder - 输入框占位符
   * @param inputPattern - 验证正则（不匹配则阻止确认）
   * @param options - 额外选项
   */
  async function confirmWithInput(
    message: string,
    inputPlaceholder: string,
    inputPattern?: RegExp,
    options: ConfirmOptions = {}
  ): Promise<boolean> {
    const {
      title = '请输入确认',
      confirmText = '确认',
      cancelText = '取消',
      type = 'warning',
    } = options

    try {
      await ElMessageBox.prompt(message, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type,
        inputPlaceholder,
        inputPattern,
        confirmButtonClass: 'el-button--danger',
      } as ElMessageBoxOptions)
      return true
    } catch {
      return false
    }
  }

  /**
   * 成功提示后确认（先提示结果，再让用户确认）
   * @param successMessage - 成功提示
   * @param confirmQuestion - 确认问题
   * @param options - 额外选项
   */
  async function confirmAfterSuccess(
    successMessage: string,
    confirmQuestion: string,
    options: ConfirmOptions = {}
  ): Promise<boolean> {
    const {
      title = '确认操作',
      confirmText = '确定',
      cancelText = '取消',
      type = 'info',
    } = options

    // 先显示成功消息
    return ElMessageBox.confirm(
      `${successMessage}\n\n${confirmQuestion}`,
      title,
      {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type,
      } as ElMessageBoxOptions
    )
      .then(() => true)
      .catch(() => false)
  }

  return {
    /** 删除确认 */
    confirmDelete,
    /** 危险操作确认 */
    confirmDangerous,
    /** 一般确认 */
    confirm,
    /** 带输入的确认 */
    confirmWithInput,
    /** 成功提示后确认 */
    confirmAfterSuccess,
  }
}

/**
 * 快捷导出：直接调用确认函数
 */
export async function confirmDelete(name?: string, options?: ConfirmOptions): Promise<boolean> {
  const { confirmDelete } = useConfirm()
  return confirmDelete(name, options)
}

export async function confirmDangerous(
  action: string,
  description?: string,
  options?: ConfirmOptions
): Promise<boolean> {
  const { confirmDangerous } = useConfirm()
  return confirmDangerous(action, description, options)
}

export async function confirm(message: string, options?: ConfirmOptions): Promise<boolean> {
  const { confirm } = useConfirm()
  return confirm(message, options)
}
