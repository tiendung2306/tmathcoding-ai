import React, { useState, useMemo } from 'react';
import { ClassStudentItemData } from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import {
  Users,
  Search,
  Filter,
  AlertOctagon,
  AlertCircle,
  Clock,
  ArrowUpDown,
  ExternalLink,
  UserCheck
} from 'lucide-react';

interface ClassStudentRosterProps {
  students: ClassStudentItemData[];
  classNameTitle: string;
  loading: boolean;
  onOpenDetailModal: (userId: number) => void;
  onSelectStudentForDashboard: (userId: number, studentName: string) => void;
}

type AlertFilter = 'ALL' | 'HAS_ALERT' | 'STUCK' | 'GAP' | 'INACTIVE';
type SortField = 'points' | 'problems' | 'name';

export const ClassStudentRoster: React.FC<ClassStudentRosterProps> = ({
  students,
  classNameTitle,
  loading,
  onOpenDetailModal,
  onSelectStudentForDashboard,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [alertFilter, setAlertFilter] = useState<AlertFilter>('ALL');
  const [sortField, setSortField] = useState<SortField>('points');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const getInitials = (name: string) => {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[parts.length - 2][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const getAlertBadge = (alert: string) => {
    switch (alert) {
      case 'STUCK':
        return (
          <Badge key="stuck" variant="wa" className="gap-1 text-[10px] py-0 px-1.5" title="Kẹt bài: trên 8 lần nộp sai trong 24 giờ">
            <AlertOctagon className="w-2.5 h-2.5" /> Kẹt bài
          </Badge>
        );
      case 'GAP':
        return (
          <Badge key="gap" variant="tle" className="gap-1 text-[10px] py-0 px-1.5" title="Hổng kiến thức nền">
            <AlertCircle className="w-2.5 h-2.5" /> Hổng kiến thức
          </Badge>
        );
      case 'INACTIVE':
        return (
          <Badge key="inactive" variant="secondary" className="gap-1 text-[10px] py-0 px-1.5" title="Chưa nộp bài trên 7 ngày">
            <Clock className="w-2.5 h-2.5" /> Ngừng nộp
          </Badge>
        );
      default:
        return null;
    }
  };

  const filteredStudents = useMemo(() => {
    return students
      .filter((st) => {
        // Search filter
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim();
          const matchName = st.name.toLowerCase().includes(q);
          const matchUser = st.username.toLowerCase().includes(q);
          const matchId = String(st.user_id).includes(q);
          if (!matchName && !matchUser && !matchId) return false;
        }

        // Alert filter
        if (alertFilter === 'HAS_ALERT') return st.alerts.length > 0;
        if (alertFilter === 'STUCK') return st.alerts.includes('STUCK');
        if (alertFilter === 'GAP') return st.alerts.includes('GAP');
        if (alertFilter === 'INACTIVE') return st.alerts.includes('INACTIVE');
        return true;
      })
      .sort((a, b) => {
        let diff = 0;
        if (sortField === 'points') diff = b.points - a.points;
        else if (sortField === 'problems') diff = b.problem_count - a.problem_count;
        else if (sortField === 'name') diff = a.name.localeCompare(b.name, 'vi');
        return sortAsc ? -diff : diff;
      });
  }, [students, searchQuery, alertFilter, sortField, sortAsc]);

  const alertCounts = useMemo(() => {
    let stuck = 0;
    let gap = 0;
    let inactive = 0;
    let any = 0;
    students.forEach((st) => {
      if (st.alerts.length > 0) any++;
      if (st.alerts.includes('STUCK')) stuck++;
      if (st.alerts.includes('GAP')) gap++;
      if (st.alerts.includes('INACTIVE')) inactive++;
    });
    return { any, stuck, gap, inactive };
  }, [students]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm flex items-center gap-2">
              <Users className="w-4 h-4 text-brand-primary" />
              Danh sách học sinh theo lớp
            </CardTitle>
            <CardDescription className="text-xs">
              Lớp: <span className="text-text-primary font-medium">{classNameTitle}</span> • {students.length} học sinh
            </CardDescription>
          </div>

          {/* Search + Quick Actions */}
          <div className="flex items-center gap-2">
            <div className="relative w-full sm:w-56">
              <Input
                type="text"
                placeholder="Lọc tên, username, mã HS..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 pl-8 pr-3 text-xs bg-card"
                aria-label="Tìm kiếm trong danh sách lớp"
              />
              <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Filter Chips Bar */}
        <div className="flex flex-wrap items-center gap-1.5 pt-3 border-t border-border/60">
          <span className="text-[11px] text-text-secondary flex items-center gap-1 mr-1">
            <Filter className="w-3 h-3 text-text-tertiary" />
            Lọc trạng thái:
          </span>

          <button
            type="button"
            onClick={() => setAlertFilter('ALL')}
            className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
              alertFilter === 'ALL'
                ? 'bg-slate-900 text-white'
                : 'bg-card-subtle text-text-secondary hover:text-text-primary hover:bg-card-hover'
            }`}
          >
            Tất cả ({students.length})
          </button>

          <button
            type="button"
            onClick={() => setAlertFilter('HAS_ALERT')}
            className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
              alertFilter === 'HAS_ALERT'
                ? 'bg-amber-600 text-white'
                : 'bg-card-subtle text-amber-700 hover:bg-card-hover'
            }`}
          >
            Cần chú ý ({alertCounts.any})
          </button>

          <button
            type="button"
            onClick={() => setAlertFilter('STUCK')}
            className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
              alertFilter === 'STUCK'
                ? 'bg-rose-600 text-white'
                : 'bg-card-subtle text-rose-700 hover:bg-card-hover'
            }`}
          >
            Kẹt bài ({alertCounts.stuck})
          </button>

          <button
            type="button"
            onClick={() => setAlertFilter('GAP')}
            className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
              alertFilter === 'GAP'
                ? 'bg-purple-600 text-white'
                : 'bg-card-subtle text-purple-700 hover:bg-card-hover'
            }`}
          >
            Hổng kiến thức ({alertCounts.gap})
          </button>

          <button
            type="button"
            onClick={() => setAlertFilter('INACTIVE')}
            className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
              alertFilter === 'INACTIVE'
                ? 'bg-slate-600 text-white'
                : 'bg-card-subtle text-text-secondary hover:bg-card-hover'
            }`}
          >
            Ngừng nộp ({alertCounts.inactive})
          </button>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {loading ? (
          <div className="p-6 text-center text-xs text-text-secondary">
            Đang tải danh sách học sinh của lớp...
          </div>
        ) : filteredStudents.length === 0 ? (
          <div className="p-8 text-center text-xs text-text-secondary space-y-1">
            <Users className="w-8 h-8 text-text-tertiary mx-auto mb-2" />
            <p className="font-medium text-text-primary">Không tìm thấy học sinh nào</p>
            <p className="text-text-tertiary">
              {searchQuery ? `Không có kết quả khớp với "${searchQuery}"` : 'Chưa có dữ liệu học sinh trong danh mục đã chọn.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto border-t border-border">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-card-subtle/70 text-text-secondary">
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider">
                    STT
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider">
                    <button
                      type="button"
                      onClick={() => toggleSort('name')}
                      className="inline-flex items-center gap-1 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary"
                    >
                      Học sinh
                      <ArrowUpDown className="w-3 h-3 text-text-tertiary" />
                    </button>
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider text-right">
                    <button
                      type="button"
                      onClick={() => toggleSort('points')}
                      className="inline-flex items-center gap-1 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary ml-auto"
                    >
                      Điểm tích lũy
                      <ArrowUpDown className="w-3 h-3 text-text-tertiary" />
                    </button>
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider text-center">
                    <button
                      type="button"
                      onClick={() => toggleSort('problems')}
                      className="inline-flex items-center gap-1 hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary"
                    >
                      Bài đã nộp
                      <ArrowUpDown className="w-3 h-3 text-text-tertiary" />
                    </button>
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider text-center">
                    Nộp gần nhất
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider text-center">
                    Trạng thái cảnh báo
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider text-right pr-4">
                    Thao tác
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredStudents.map((st, idx) => (
                  <tr
                    key={st.user_id}
                    className="hover:bg-card-hover/40 transition-colors group"
                  >
                    <td className="py-2.5 px-3 font-mono text-[11px] text-text-tertiary">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-sm bg-brand-primary/10 border border-brand-primary/20 text-brand-primary font-mono text-[10px] font-semibold flex items-center justify-center shrink-0">
                          {getInitials(st.name)}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-text-primary truncate" title={st.name}>
                              {st.name}
                            </span>
                            <Badge variant="outline" className="text-[9px] font-mono py-0 px-1">
                              #{st.user_id}
                            </Badge>
                          </div>
                          <span className="text-[11px] text-text-secondary truncate block">
                            @{st.username}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span className="font-mono font-bold text-text-primary text-xs">
                        {st.points.toLocaleString('vi-VN')}
                      </span>
                      <span className="text-[10px] text-text-tertiary block capitalize">
                        {st.display_rank}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="font-mono text-text-primary font-medium text-xs">
                        {st.problem_count}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center font-mono text-[11px] text-text-secondary">
                      {st.last_submission_at ? (
                        <span>{new Date(st.last_submission_at).toLocaleDateString('vi-VN')}</span>
                      ) : (
                        <span className="text-text-disabled">Chưa nộp</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <div className="flex flex-wrap items-center justify-center gap-1">
                        {st.alerts.map((alt) => getAlertBadge(alt))}
                        {st.alerts.length === 0 && (
                          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700">
                            <UserCheck className="w-3 h-3" /> Bình thường
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right pr-4">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onOpenDetailModal(st.user_id)}
                          className="h-7 px-2 text-[11px] font-normal text-text-secondary hover:text-text-primary"
                          title="Xem hồ sơ chi tiết và phân bố Bloom"
                        >
                          Hồ sơ
                        </Button>
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => onSelectStudentForDashboard(st.user_id, st.name)}
                          className="h-7 px-2.5 text-[11px] font-medium gap-1"
                          title="Mở bảng phân tích học lực của học sinh"
                        >
                          <span>Học lực</span>
                          <ExternalLink className="w-3 h-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
