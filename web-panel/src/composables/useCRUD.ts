/**
 * CRUD 组合式函数 - 封装通用增删改查逻辑
 *
 * 功能：
 * - 通用列表获取、分页、刷新
 * - 统一 loading 状态管理
 * - 统一错误处理
 * - 支持自定义格式化、转换
 *
 * @example
 * const { data, loading, fetchData, create, update, remove } = useCRUD({
 *   fetchApi: () => request.get('/users'),
 *   createApi: (data) => request.post('/users', data),
 *   updateApi: (id, data) => request.put(`/users/${id}`, data),
 *   deleteApi: (id) => request.delete(`/users/${id}`),
 *   onSuccess: (action, data) => ElMessage.success('操作成功'),
 * })
 */
import { ref, reactive, computed, type Ref, type ComputedRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

/**
 * 分页参数
 */
export interface PaginationParams {
  page: number
  page_size: number
}

/**
 * 分页响应
 */
export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/**
 * CRUD 配置选项
 */
export interface UseCRUDOptions<T, CreateDTO = any, UpdateDTO = CreateDTO> {
  /** 获取列表数据（支持分页） */
  fetchApi: (params?: PaginationParams) => Promise<PaginatedData<T> | T[]>
  /** 创建数据 */
  createApi?: (data: CreateDTO) => Promise<T>
  /** 更新数据 */
  updateApi?: (id: number, data: UpdateDTO) => Promise<T>
  /** 删除数据 */
  deleteApi?: (id: number) => Promise<void>
  /** 是否启用分页（默认 true） */
  enablePagination?: boolean
  /** 默认分页大小 */
  defaultPageSize?: number
  /** 成功消息（可自定义每个操作的消息） */
  successMessage?: string | { create?: string; update?: string; delete?: string }
  /** 成功回调 */
  onSuccess?: (action: 'create' | 'update' | 'delete' | 'fetch', data?: any) => void
  /** 错误回调 */
  onError?: (action: 'create' | 'update' | 'delete' | 'fetch', error: any) => void
  /** 格式化列表数据 */
  formatData?: (item: any) => T
}

/**
 * CRUD 状态
 */
export interface UseCRUDState<T> {
  /** 列表数据 */
  data: Ref<T[]>
  /** 是否加载中 */
  loading: Ref<boolean>
  /** 是否保存中（用于创建/更新操作） */
  saving: Ref<boolean>
  /** 是否删除中 */
  deleting: Ref<boolean>
  /** 分页信息 */
  pagination: {
    page: number
    pageSize: number
    total: number
  }
  /** 当前操作对应的 ID（用于编辑等场景） */
  currentId: Ref<number | null>
}

/**
 * CRUD 方法
 */
export interface UseCRUDMethods<T, CreateDTO = any, UpdateDTO = CreateDTO> {
  /** 获取数据（带分页） */
  fetchData: (params?: Partial<PaginationParams>) => Promise<void>
  /** 刷新数据（保持当前分页） */
  refresh: () => Promise<void>
  /** 创建数据 */
  create: (data: CreateDTO) => Promise<T | null>
  /** 更新数据 */
  update: (id: number, data: UpdateDTO) => Promise<T | null>
  /** 删除数据 */
  remove: (id: number, name?: string) => Promise<boolean>
  /** 设置当前编辑项 ID */
  setCurrentId: (id: number | null) => void
  /** 重置分页 */
  resetPagination: () => void
}

/**
 * useCRUD 组合式函数
 */
export function useCRUD<T extends { id: number }, CreateDTO = any, UpdateDTO = CreateDTO>(
  options: UseCRUDOptions<T, CreateDTO, UpdateDTO>
): UseCRUDState<T> & UseCRUDMethods<T, CreateDTO, UpdateDTO> {
  const {
    fetchApi,
    createApi,
    updateApi,
    deleteApi,
    enablePagination = true,
    defaultPageSize = 20,
    successMessage,
    onSuccess,
    onError,
    formatData,
  } = options

  // ========== 状态 ==========

  /** 列表数据 */
  const data = ref<T[]>([]) as Ref<T[]>

  /** 是否加载中 */
  const loading = ref(false)

  /** 是否保存中 */
  const saving = ref(false)

  /** 是否删除中 */
  const deleting = ref(false)

  /** 分页信息 */
  const pagination = reactive({
    page: 1,
    pageSize: defaultPageSize,
    total: 0,
  })

  /** 当前操作对应的 ID */
  const currentId = ref<number | null>(null)

  // ========== 工具方法 ==========

  /**
   * 获取成功消息
   */
  function getSuccessMessage(action: 'create' | 'update' | 'delete'): string {
    if (typeof successMessage === 'string') {
      return successMessage
    }
    if (successMessage && typeof successMessage === 'object') {
      return successMessage[action] || `${action === 'create' ? '创建' : action === 'update' ? '更新' : '删除'}成功`
    }
    return `${action === 'create' ? '创建' : action === 'update' ? '更新' : '删除'}成功`
  }

  /**
   * 调用成功回调
   */
  function callOnSuccess(action: 'create' | 'update' | 'delete' | 'fetch', result?: any) {
    if (onSuccess) {
      try {
        onSuccess(action, result)
      } catch (e) {
        console.error('onSuccess callback error:', e)
      }
    }
  }

  /**
   * 调用错误回调
   */
  function callOnError(action: 'create' | 'update' | 'delete' | 'fetch', error: any) {
    if (onError) {
      try {
        onError(action, error)
      } catch (e) {
        console.error('onError callback error:', e)
      }
    }
  }

  /**
   * 格式化单条数据
   */
  function formatItem(item: any): T {
    if (formatData) {
      return formatData(item)
    }
    return item as T
  }

  /**
   * 格式化列表数据
   */
  function formatList(items: any[]): T[] {
    return items.map(formatItem)
  }

  // ========== CRUD 方法 ==========

  /**
   * 获取数据
   */
  async function fetchData(params?: Partial<PaginationParams>): Promise<void> {
    // 如果传入了分页参数，更新分页状态
    if (params) {
      if (params.page !== undefined) pagination.page = params.page
      if (params.page_size !== undefined) pagination.pageSize = params.page_size
    }

    loading.value = true

    try {
      const fetchParams = enablePagination
        ? { page: pagination.page, page_size: pagination.pageSize }
        : undefined

      const result = await fetchApi(fetchParams)

      if (Array.isArray(result)) {
        // 非分页响应
        data.value = formatList(result)
        pagination.total = result.length
      } else if (result && 'items' in result) {
        // 分页响应
        data.value = formatList(result.items)
        pagination.total = result.total || result.items.length
      } else {
        data.value = formatList(Array.isArray(result) ? result : [result])
      }

      callOnSuccess('fetch')
    } catch (error) {
      callOnError('fetch', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 刷新数据
   */
  async function refresh(): Promise<void> {
    await fetchData()
  }

  /**
   * 创建数据
   */
  async function create(dto: CreateDTO): Promise<T | null> {
    if (!createApi) {
      console.warn('createApi not provided')
      return null
    }

    saving.value = true

    try {
      const result = await createApi(dto)
      const formatted = formatItem(result)

      // 如果列表还没满，可以直接添加到列表头部
      if (data.value.length < pagination.pageSize) {
        data.value.unshift(formatted)
        pagination.total++
      }

      ElMessage.success(getSuccessMessage('create'))
      callOnSuccess('create', formatted)

      return formatted
    } catch (error) {
      callOnError('create', error)
      return null
    } finally {
      saving.value = false
    }
  }

  /**
   * 更新数据
   */
  async function update(id: number, dto: UpdateDTO): Promise<T | null> {
    if (!updateApi) {
      console.warn('updateApi not provided')
      return null
    }

    saving.value = true

    try {
      const result = await updateApi(id, dto)
      const formatted = formatItem(result)

      // 更新列表中的对应项
      const index = data.value.findIndex((item) => item.id === id)
      if (index > -1) {
        data.value[index] = formatted
      }

      ElMessage.success(getSuccessMessage('update'))
      callOnSuccess('update', formatted)

      return formatted
    } catch (error) {
      callOnError('update', error)
      return null
    } finally {
      saving.value = false
    }
  }

  /**
   * 删除数据
   */
  async function remove(id: number, name?: string): Promise<boolean> {
    if (!deleteApi) {
      console.warn('deleteApi not provided')
      return false
    }

    try {
      await ElMessageBox.confirm(
        name ? `确定要删除「${name}」吗？此操作不可撤销。` : '确定要删除吗？此操作不可撤销。',
        '删除确认',
        {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      deleting.value = true

      try {
        await deleteApi(id)

        // 从列表中移除
        const index = data.value.findIndex((item) => item.id === id)
        if (index > -1) {
          data.value.splice(index, 1)
          pagination.total--
        }

        ElMessage.success(getSuccessMessage('delete'))
        callOnSuccess('delete')

        return true
      } catch (error) {
        callOnError('delete', error)
        return false
      } finally {
        deleting.value = false
      }
    } catch {
      // 用户取消
      return false
    }
  }

  /**
   * 设置当前 ID
   */
  function setCurrentId(id: number | null) {
    currentId.value = id
  }

  /**
   * 重置分页
   */
  function resetPagination() {
    pagination.page = 1
    pagination.pageSize = defaultPageSize
    pagination.total = 0
  }

  return {
    // 状态
    data,
    loading,
    saving,
    deleting,
    pagination,
    currentId,
    // 方法
    fetchData,
    refresh,
    create,
    update,
    remove,
    setCurrentId,
    resetPagination,
  }
}

/**
 * 简化版 useCRUD（仅列表）
 */
export function useFetchList<T>(
  fetchApi: () => Promise<T[]>,
  options?: {
    formatData?: (item: any) => T
    onSuccess?: (data: T[]) => void
    onError?: (error: any) => void
  }
) {
  const data = ref<T[]>([]) as Ref<T[]>
  const loading = ref(false)

  async function fetch() {
    loading.value = true
    try {
      const result = await fetchApi()
      const items = Array.isArray(result) ? result : [result]
      data.value = options?.formatData ? items.map(options.formatData) : (items as T[])
      options?.onSuccess?.(data.value)
    } catch (error) {
      options?.onError?.(error)
    } finally {
      loading.value = false
    }
  }

  return {
    data,
    loading,
    fetch,
  }
}
