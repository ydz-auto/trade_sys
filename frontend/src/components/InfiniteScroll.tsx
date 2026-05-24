/**
 * InfiniteScroll - 无限滚动加载组件
 * 
 * 用于新闻、社交帖子等分页内容的滚动加载
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { Spin, Empty } from 'antd'

interface InfiniteScrollProps<T> {
  // 数据加载函数
  fetchData: (page: number, pageSize: number) => Promise<{
    items: T[]
    total: number
    hasMore: boolean
  }>
  // 渲染每一项的函数
  renderItem: (item: T, index: number) => React.ReactNode
  // 每页数量
  pageSize?: number
  // 初始数据
  initialData?: T[]
  // 加载更多时的提示
  loadingText?: string
  // 空数据提示
  emptyText?: string
  // 容器样式
  className?: string
  // 容器最大高度
  maxHeight?: string
}

export function InfiniteScroll<T>({
  fetchData,
  renderItem,
  pageSize = 10,
  initialData = [],
  loadingText = '加载中...',
  emptyText = '暂无数据',
  className = '',
  maxHeight = '400px',
}: InfiniteScrollProps<T>) {
  const [items, setItems] = useState<T[]>(initialData)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [total, setTotal] = useState(0)
  
  const containerRef = useRef<HTMLDivElement>(null)
  const loadingRef = useRef(false)

  // 加载第一页数据
  useEffect(() => {
    loadMore(1)
  }, [])

  const loadMore = useCallback(async (pageNum: number) => {
    if (loadingRef.current) return
    loadingRef.current = true
    setLoading(true)

    try {
      const result = await fetchData(pageNum, pageSize)
      
      if (pageNum === 1) {
        setItems(result.items)
      } else {
        setItems(prev => [...prev, ...result.items])
      }
      
      setTotal(result.total)
      setHasMore(result.hasMore)
      setPage(pageNum)
    } catch (error) {
      console.error('Error loading more data:', error)
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }, [fetchData, pageSize])

  // 滚动事件处理
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      if (loading || !hasMore) return

      const { scrollTop, scrollHeight, clientHeight } = container
      // 距离底部 100px 时触发加载
      if (scrollHeight - scrollTop - clientHeight < 100) {
        loadMore(page + 1)
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [loading, hasMore, page, loadMore])

  return (
    <div
      ref={containerRef}
      className={`overflow-y-auto ${className}`}
      style={{ maxHeight }}
    >
      {items.length === 0 && !loading ? (
        <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <>
          {items.map((item, index) => renderItem(item, index))}
          
          {loading && (
            <div className="flex justify-center py-4">
              <Spin tip={loadingText} />
            </div>
          )}
          
          {!hasMore && items.length > 0 && (
            <div className="text-center py-4 text-gray-400 text-sm">
              已加载全部 {total} 条数据
            </div>
          )}
        </>
      )}
    </div>
  )
}

/**
 * useInfiniteScroll - 无限滚动 Hook
 * 
 * 用于自定义实现无限滚动
 */
export function useInfiniteScroll<T>(
  fetchData: (page: number, pageSize: number) => Promise<{
    items: T[]
    total: number
    hasMore: boolean
  }>,
  pageSize: number = 10
) {
  const [items, setItems] = useState<T[]>([])
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<Error | null>(null)

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    
    setLoading(true)
    setError(null)

    try {
      const nextPage = page + 1
      const result = await fetchData(nextPage, pageSize)
      
      setItems(prev => [...prev, ...result.items])
      setTotal(result.total)
      setHasMore(result.hasMore)
      setPage(nextPage)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, loading, hasMore, fetchData])

  const refresh = useCallback(async () => {
    setItems([])
    setPage(0)
    setHasMore(true)
    setError(null)
    
    setLoading(true)
    try {
      const result = await fetchData(1, pageSize)
      setItems(result.items)
      setTotal(result.total)
      setHasMore(result.hasMore)
      setPage(1)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setLoading(false)
    }
  }, [pageSize, fetchData])

  return {
    items,
    loading,
    hasMore,
    total,
    error,
    loadMore,
    refresh,
    page,
  }
}
