import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scoreDate, studentScore } from '../services/scoring';

export function StudentAchievement({ studentId }: { studentId: number }) {
  const [page, setPage] = useState(1);
  const score = useQuery({ queryKey: ['student-score', studentId, page], queryFn: () => studentScore(studentId, page) });
  if (score.isPending) return <p role="status" className="text-sm">Đang tải điểm thành tích...</p>;
  if (score.isError) return <div role="alert" className="text-sm">Không tải được điểm thành tích. <button className="min-h-11 underline" onClick={() => void score.refetch()}>Thử lại</button></div>;
  if (!score.data) return null;
  if (!score.data.ready) return <p className="text-sm text-text-secondary">Học sinh chưa có trong snapshot điểm hiện tại.</p>;
  const data = score.data;
  return <section className="space-y-3 rounded-md border border-border bg-card p-4">
    <h2 className="text-lg font-medium">Điểm thành tích: <span className="tabular-nums">{data.points.toLocaleString('vi-VN')}</span></h2>
    <p className="text-sm text-text-secondary">{data.solved_count} bài AC riêng biệt. Dữ liệu đến {scoreDate(data.as_of)}.</p>
    <details><summary className="min-h-11 cursor-pointer text-sm">Xem các bài đóng góp điểm</summary><ul className="divide-y divide-border">{data.items.map(item => <li key={item.problem_id} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><span className="min-w-0 break-words">{item.code} · {item.title}</span><span>{item.points.toLocaleString('vi-VN')} điểm</span></li>)}</ul>{!data.items.length && <p className="py-3 text-sm text-text-secondary">Chưa có bài AC trong snapshot.</p>}{data.total_pages > 1 && <div className="flex flex-wrap items-center justify-between gap-3"><button className="min-h-11 px-3 underline disabled:opacity-50" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trang trước</button><span className="text-sm">{page}/{data.total_pages}</span><button className="min-h-11 px-3 underline disabled:opacity-50" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>Trang sau</button></div>}</details>
  </section>;
}
