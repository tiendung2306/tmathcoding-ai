import React, { useState, useMemo } from 'react';
import { ClassStudentItemData } from '../types';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';
import {
  Users,
  Search,
  ArrowLeft,
  ArrowUpDown,
  AlertOctagon,
  AlertCircle,
  Clock,
  ChevronRight,
  UserCheck,
  Award,
  CheckCircle2,
  FileCode2
} from 'lucide-react';

interface ClassStudentsGridProps {
  classNameTitle: string;
  classId: number;
  students: ClassStudentItemData[];
  loading: boolean;
  onSelectStudent: (userId: number, studentName: string) => void;
  onBackToClasses: () => void;
}

type AlertFilter = 'ALL' | 'HAS_ALERT' | 'STUCK' | 'GAP' | 'INACTIVE';
type SortField = 'points' | 'problems' | 'name';

export const ClassStudentsGrid: React.FC<ClassStudentsGridProps> = ({
  classNameTitle,
  classId,
  students,
  loading,
  onSelectStudent,
  onBackToClasses,
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
          <Badge
            key="stuck"
            variant="wa"
            className="gap-1 text-[10px] py-0 px-1.5"
            title="Kẹt bài: trên 8 lần nộp sai trong 24 giờ"
          >
            <AlertOctagon className="w-2.5 h-2.5" /> Kẹt bài
          </Badge>
        );
      case 'GAP':
        return (
          <Badge
            key="gap"
            variant="tle"
            className="gap-1 text-[10px] py-0 px-1.5"
            title="Hổng kiến thức nền"
          >
            <AlertCircle className="w-2.5 h-2.5" /> Hổng kiến thức
          </Badge>
        );
      case 'INACTIVE':
        return (
          <Badge
            key="inactive"
            variant="secondary"
            className="gap-1 text-[10px] py-0 px-1.5"
            title="Chưa nộp bài trên 7 ngày"
          >
            <Clock className="w-2.5 h-2.5" /> Ngừng nộp
          </Badge>
        );
      default:
        return null;
    }
  };

  // Filter and sort students
  const filteredStudents = useMemo(() => {
    let list = [...students];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.username.toLowerCase().includes(q) ||
          s.user_id.toString().includes(q)
      );
    }

    if (alertFilter === 'HAS_ALERT') {
      list = list.filter((s) => s.alerts && s.alerts.length > 0);
    } else if (alertFilter === 'STUCK') {
      list = list.filter((s) => s.alerts && s.alerts.includes('STUCK'));
    } else if (alertFilter === 'GAP') {
      list = list.filter((s) => s.alerts && s.alerts.includes('GAP'));
    } else if (alertFilter === 'INACTIVE') {
      list = list.filter((s) => s.alerts && s.alerts.includes('INACTIVE'));
    }

    list.sort((a, b) => {
      let diff = 0;
      if (sortField === 'points') {
        diff = b.points - a.points;
      } else if (sortField === 'problems') {
        diff = b.problem_count - a.problem_count;
      } else if (sortField === 'name') {
        diff = a.name.localeCompare(b.name, 'vi', { numeric: true });
      }
      return sortAsc ? -diff : diff;
    });

    return list;
  }, [students, searchQuery, alertFilter, sortField, sortAsc]);

  // Statistics
  const stats = useMemo(() => {
    const total = students.length;
    let withAlerts = 0;
    let stuck = 0;
    let gap = 0;
    let inactive = 0;

    students.forEach((s) => {
      if (s.alerts && s.alerts.length > 0) withAlerts++;
      if (s.alerts && s.alerts.includes('STUCK')) stuck++;
      if (s.alerts && s.alerts.includes('GAP')) gap++;
      if (s.alerts && s.alerts.includes('INACTIVE')) inactive++;
    });

    return { total, withAlerts, stuck, gap, inactive };
  }, [students]);

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onBackToClasses}
          className="h-8 px-2.5 text-xs gap-1.5 text-text-secondary hover:text-text-primary"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Quay lại danh sách lớp</span>
        </Button>

        <div className="text-xs text-text-tertiary">
          <span>Lớp #{classId}</span>
        </div>
      </div>

      {/* Class Title Header */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight">
                {classNameTitle}
              </h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                {students.length} học sinh
              </Badge>
            </div>
            <p className="text-xs text-text-secondary">
              Bấm vào học sinh để xem biểu đồ năng lực đa chiều và gợi ý ôn tập AI
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <div className="relative w-full sm:w-56">
              <Input
                type="text"
                placeholder="Tìm học sinh theo tên, ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 h-8 text-xs bg-card"
              />
              <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
            </div>

            {/* Sort Selector */}
            <div className="flex items-center gap-1.5 bg-card-subtle px-2 py-1 rounded-md border border-border">
              <ArrowUpDown className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0" />
              <label htmlFor="student-sort-select" className="sr-only">Sắp xếp học sinh</label>
              <select
                id="student-sort-select"
                value={sortField}
                onChange={(e) => setSortField(e.target.value as SortField)}
                className="bg-transparent text-xs text-text-primary rounded-md cursor-pointer pr-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              >
                <option value="points" className="bg-card text-text-primary">
                  Điểm số (Cao → Thấp)
                </option>
                <option value="problems" className="bg-card text-text-primary">
                  Số bài nộp (Nhiều → Ít)
                </option>
                <option value="name" className="bg-card text-text-primary">
                  Tên học sinh (A → Z)
                </option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => setAlertFilter('ALL')}
          className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
            alertFilter === 'ALL'
              ? 'bg-brand-primary/10 text-brand-primary border-brand-primary/30'
              : 'bg-card text-text-secondary border-border hover:text-text-primary'
          }`}
        >
          Tất cả ({stats.total})
        </button>

        {stats.withAlerts > 0 && (
          <button
            type="button"
            onClick={() => setAlertFilter('HAS_ALERT')}
            className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
              alertFilter === 'HAS_ALERT'
                ? 'bg-amber-500/10 text-amber-600 border-amber-500/30'
                : 'bg-card text-text-secondary border-border hover:text-text-primary'
            }`}
          >
            Có cảnh báo ({stats.withAlerts})
          </button>
        )}

        {stats.stuck > 0 && (
          <button
            type="button"
            onClick={() => setAlertFilter('STUCK')}
            className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
              alertFilter === 'STUCK'
                ? 'bg-amber-500/10 text-amber-600 border-amber-500/30'
                : 'bg-card text-text-secondary border-border hover:text-text-primary'
            }`}
          >
            Kẹt bài ({stats.stuck})
          </button>
        )}

        {stats.gap > 0 && (
          <button
            type="button"
            onClick={() => setAlertFilter('GAP')}
            className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
              alertFilter === 'GAP'
                ? 'bg-purple-500/10 text-purple-600 border-purple-500/30'
                : 'bg-card text-text-secondary border-border hover:text-text-primary'
            }`}
          >
            Hổng kiến thức ({stats.gap})
          </button>
        )}

        {stats.inactive > 0 && (
          <button
            type="button"
            onClick={() => setAlertFilter('INACTIVE')}
            className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
              alertFilter === 'INACTIVE'
                ? 'bg-slate-500/10 text-slate-600 border-slate-500/30'
                : 'bg-card text-text-secondary border-border hover:text-text-primary'
            }`}
          >
            Ngừng nộp ({stats.inactive})
          </button>
        )}
      </div>

      {/* Grid of Students */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : filteredStudents.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center space-y-2">
            <Users className="w-8 h-8 text-text-tertiary mx-auto opacity-50" />
            <p className="text-sm font-medium text-text-primary">Không tìm thấy học sinh nào</p>
            <p className="text-xs text-text-secondary">
              Vui lòng thử lại với từ khóa hoặc bộ lọc khác.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
          {filteredStudents.map((st) => (
            <div
              key={st.user_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectStudent(st.user_id, st.name)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectStudent(st.user_id, st.name);
                }
              }}
              className="bg-card border border-border hover:border-brand-primary/60 hover:shadow-xs p-4 rounded-lg cursor-pointer transition-all duration-150 flex flex-col justify-between group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              <div className="space-y-3">
                {/* User Top Row: Avatar Initials + ID */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-7 h-7 rounded-md bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-xs font-semibold text-brand-primary shrink-0 font-mono">
                      {getInitials(st.name)}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-xs sm:text-sm font-semibold text-text-primary group-hover:text-brand-primary transition-colors truncate">
                        {st.name}
                      </h3>
                      <p className="text-[10px] font-mono text-text-tertiary">
                        #{st.user_id} • @{st.username}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Score & Submissions */}
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                    <span className="text-[10px] text-text-secondary block">Điểm số</span>
                    <span className="font-mono font-bold text-text-primary text-xs">
                      {st.points.toLocaleString('vi-VN')}
                    </span>
                  </div>
                  <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                    <span className="text-[10px] text-text-secondary block">Bài nộp</span>
                    <span className="font-mono font-semibold text-text-primary text-xs">
                      {st.problem_count}
                    </span>
                  </div>
                </div>

                {/* Alerts if any */}
                {st.alerts && st.alerts.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {st.alerts.map((a) => getAlertBadge(a))}
                  </div>
                )}
              </div>

              <div className="pt-2.5 mt-3 border-t border-border/50 flex items-center justify-between text-[11px] text-text-tertiary group-hover:text-brand-primary transition-colors">
                <span>Xem chi tiết số liệu</span>
                <ChevronRight className="w-3.5 h-3.5 transform group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
