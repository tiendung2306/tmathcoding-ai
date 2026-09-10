import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import {
  fetchAutoTagStatus,
  runAutoTagBatch
} from '../services/api';
import {
  AutoTagStatusResponseData
} from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { ErrorPanel } from '../components/ErrorPanel';
import {
  Cpu,
  RefreshCw,
  Play,
  CheckCircle2,
  AlertCircle,
  FileCode,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const [statusData, setStatusData] = useState<AutoTagStatusResponseData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [batchSize, setBatchSize] = useState<number>(10);
  const [isTriggering, setIsTriggering] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedReasonId, setExpandedReasonId] = useState<number | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadStatus = async (isSilent: boolean = false) => {
    if (!isSilent) setLoading(true);
    setError(null);
    try {
      const data = await fetchAutoTagStatus();
      setStatusData(data);
    } catch (err) {
      console.error(err);
      if (!isSilent) {
        setError('Không thể kết nối đến máy chủ để lấy trạng thái gắn nhãn. Vui lòng thử lại.');
      }
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  // Polling tự động khi tiến trình worker đang chạy
  useEffect(() => {
    if (statusData?.is_running) {
      pollingRef.current = setInterval(() => {
        loadStatus(true);
      }, 2500);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [statusData?.is_running]);

  const handleStartBatch = async () => {
    setIsTriggering(true);
    setActionMessage(null);
    try {
      const res = await runAutoTagBatch(batchSize);
      setActionMessage({
        type: 'success',
        text: res.message || `Đã khởi động tiến trình gắn nhãn cho ${batchSize} bài toán.`
      });
      // Tải lại trạng thái để kích hoạt polling
      await loadStatus(true);
    } catch (err) {
      console.error(err);
      const detail = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: string } | undefined)?.detail
        : undefined;
      setActionMessage({
        type: 'error',
        text: detail || 'Không thể bắt đầu tiến trình gắn nhãn. Vui lòng thử lại.'
      });
    } finally {
      setIsTriggering(false);
    }
  };

  const toggleReasonExpand = (id: number) => {
    setExpandedReasonId(expandedReasonId === id ? null : id);
  };

  if (loading) {
    return (
      <div className="p-5 max-w-7xl mx-auto space-y-4">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-24" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <ErrorPanel message={error} onRetry={() => loadStatus()} />
      </div>
    );
  }

  const isRunning = statusData?.is_running || false;
  const currentBatch = statusData?.current_batch;
  const progressPercent = statusData?.progress_percentage || 0;
  const recentTags = statusData?.recent_tags || [];

  return (
    <div className="p-5 max-w-7xl mx-auto space-y-4">
      {/* Header gọn: tiêu đề + trạng thái worker + hành động */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <Cpu className="w-4 h-4 text-brand-primary shrink-0" />
          <h1 className="text-sm font-semibold text-text-primary whitespace-nowrap">
            Gắn nhãn tự động
          </h1>
          {isRunning ? (
            <Badge variant="running" className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              Đang xử lý
            </Badge>
          ) : (
            <Badge variant="ac" className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
              Sẵn sàng
            </Badge>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => loadStatus()}
          className="flex items-center gap-1.5 text-xs"
          disabled={loading}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Làm mới
        </Button>
      </div>

      {/* Thông báo thao tác */}
      {actionMessage && (
        <div
          role="alert"
          className={`p-3 rounded-md text-xs flex items-center justify-between border ${
            actionMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="text-xs font-semibold hover:opacity-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded-xs px-1"
          >
            Đóng
          </button>
        </div>
      )}

      {/* Tiến độ + điều khiển batch: một khối duy nhất, một nguồn sự thật */}
      <Card className="bg-card">
        <CardContent className="p-4 space-y-3">
          {/* Dòng tiến độ chính: X / Y bài + thanh + % */}
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-text-primary font-mono whitespace-nowrap">
              {statusData?.tagged_problems ?? 0}
              <span className="text-text-tertiary font-normal"> / {statusData?.total_problems?.toLocaleString() ?? 0}</span>
            </span>
            <span className="text-xs text-text-secondary whitespace-nowrap">bài đã gắn nhãn</span>
            <div className="flex-1 h-1.5 bg-card-subtle rounded-full overflow-hidden border border-border min-w-[80px]">
              <div
                className="h-full bg-slate-900 transition-all duration-300 rounded-full"
                style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
              />
            </div>
            <span className="text-xs font-mono text-text-secondary w-12 text-right">{progressPercent}%</span>
          </div>

          {/* Dòng batch đang chạy: chỉ hiện khi worker hoạt động */}
          {isRunning && currentBatch && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-secondary bg-card-subtle border border-border rounded-md px-3 py-2">
              <span className="font-medium text-text-primary">
                Đang xử lý <span className="font-mono">{currentBatch.processed} / {currentBatch.total}</span> bài
              </span>
              <span>Thành công: <strong className="text-emerald-700 font-mono">{currentBatch.successful}</strong></span>
              <span>Lỗi: <strong className="text-red-700 font-mono">{currentBatch.failed}</strong></span>
              <span>từ <span className="font-mono">{currentBatch.started_at}</span></span>
            </div>
          )}

          {/* Hàng điều khiển */}
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="batch-size-select" className="text-xs text-text-secondary whitespace-nowrap">
              Số lượng bài mỗi đợt:
            </label>
            <select
              id="batch-size-select"
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              disabled={isRunning || isTriggering}
              className="h-8 rounded-md border border-border bg-card px-2.5 text-xs text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              <option value={5}>5 bài toán</option>
              <option value={10}>10 bài toán</option>
              <option value={20}>20 bài toán</option>
              <option value={50}>50 bài toán</option>
            </select>
            <Button
              variant="default"
              size="default"
              onClick={handleStartBatch}
              disabled={isRunning || isTriggering || (statusData?.untagged_problems === 0)}
              className="flex items-center gap-1.5"
            >
              {isRunning || isTriggering ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Đang gắn nhãn...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Bắt đầu gắn nhãn</span>
                </>
              )}
            </Button>
            {statusData?.untagged_problems === 0 && (
              <span className="text-xs text-emerald-700 font-medium">
                Tất cả bài toán trong hệ thống đã được gắn nhãn đầy đủ.
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Bảng 10 bài toán gắn nhãn gần nhất */}
      <Card className="bg-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Các bài toán vừa được gắn nhãn</CardTitle>
              <CardDescription>
                Danh sách 10 bài toán được AI phân loại gần nhất trong hệ thống.
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs font-mono">
              {recentTags.length} bài gần nhất
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {recentTags.length === 0 ? (
            <div className="p-8 text-center text-text-secondary text-xs">
              <FileCode className="w-8 h-8 text-text-tertiary mx-auto mb-2" />
              <p className="font-medium text-text-primary">Chưa có bài toán nào được gắn nhãn</p>
              <p className="text-text-secondary mt-1">
                Hãy chọn số lượng bài và nhấn &quot;Bắt đầu gắn nhãn&quot; ở trên để khởi chạy đợt phân loại đầu tiên.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border bg-card-subtle/50 text-text-secondary">
                    <th scope="col" className="py-2 px-4 font-medium">Bài toán</th>
                    <th scope="col" className="py-2 px-4 font-medium">Chủ đề chính</th>
                    <th scope="col" className="py-2 px-4 font-medium">Mức Bloom</th>
                    <th scope="col" className="py-2 px-4 font-medium">Lý do phân loại</th>
                    <th scope="col" className="py-2 px-4 font-medium">Thời gian</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {recentTags.map((item) => {
                    const isExpanded = expandedReasonId === item.id;
                    return (
                      <tr key={item.id} className="hover:bg-card-hover/40 transition-colors">
                        <td className="py-2 px-4 max-w-[240px]">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="font-mono text-[11px] font-medium text-text-primary whitespace-nowrap">
                              {item.problem_code}
                            </span>
                            <span className="text-text-tertiary shrink-0">·</span>
                            <span className="text-text-primary truncate" title={item.problem_name}>
                              {item.problem_name}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-4 whitespace-nowrap">
                          <Badge variant="outline" className="text-[11px] font-normal">
                            {item.primary_tag_name}
                          </Badge>
                        </td>
                        <td className="py-2 px-4 whitespace-nowrap">
                          <Badge variant="secondary" className="text-[11px]">
                            {item.bloom_group_name || 'Chưa xác định'}
                          </Badge>
                        </td>
                        <td className="py-2 px-4 text-text-secondary max-w-xs">
                          <div>
                            <p className={`leading-relaxed ${isExpanded ? '' : 'line-clamp-2'}`}>
                              {item.reasoning || 'Phân tích tự động dựa trên mã nguồn AC và giới hạn bài toán.'}
                            </p>
                            {item.reasoning && item.reasoning.length > 90 && (
                              <button
                                type="button"
                                onClick={() => toggleReasonExpand(item.id)}
                                className="text-[11px] text-brand-primary hover:underline mt-0.5 inline-flex items-center gap-0.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary"
                              >
                                {isExpanded ? (
                                  <>
                                    Thu gọn <ChevronUp className="w-3 h-3" />
                                  </>
                                ) : (
                                  <>
                                    Xem thêm <ChevronDown className="w-3 h-3" />
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="py-2 px-4 text-text-tertiary whitespace-nowrap font-mono text-[11px]" title={item.created_at}>
                          {item.created_at?.slice(11, 16)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
