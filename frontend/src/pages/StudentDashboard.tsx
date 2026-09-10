import React, { useEffect, useState, useMemo } from 'react';
import {
  fetchSkillTree,
  fetchTagAnalytics,
  fetchAICommentary,
} from '../services/api';
import {
  SkillTreeResponseData,
  TagAnalyticsResponseData,
  AICommentaryResponseData,
  ClassStudentItemData,
  TimeRange,
} from '../types';
import { BloomRadar } from '../components/BloomRadar';
import { SkillTree } from '../components/SkillTree';
import { AIAdvisorCard } from '../components/AIAdvisorCard';
import { TagCompletionGrid } from '../components/TagCompletionGrid';
import { TimeRangeFilter } from '../components/TimeRangeFilter';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface StudentDashboardProps {
  studentId: number;
  classStudents?: ClassStudentItemData[];
  currentClassName?: string;
  onSelectStudent?: (userId: number, name: string) => void;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({
  studentId,
  classStudents = [],
  currentClassName,
  onSelectStudent,
}) => {
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [data, setData] = useState<SkillTreeResponseData | null>(null);
  const [tagData, setTagData] = useState<TagAnalyticsResponseData | null>(null);
  const [aiData, setAiData] = useState<AICommentaryResponseData | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(true);
  const [aiRefreshing, setAiRefreshing] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData(timeRange);
  }, [studentId]);

  const loadData = async (range: TimeRange = timeRange) => {
    setLoading(true);
    setError(null);
    loadAICommentary(false, range);
    try {
      const [skillRes, tagRes] = await Promise.allSettled([
        fetchSkillTree(studentId, range),
        fetchTagAnalytics(studentId, range),
      ]);
      if (skillRes.status === 'fulfilled') {
        setData(skillRes.value);
      } else {
        setError('Không tải được sơ đồ kỹ năng của học sinh. Vui lòng thử lại sau.');
      }
      if (tagRes.status === 'fulfilled') setTagData(tagRes.value);
    } catch (err) {
      console.error(err);
      setError('Không tải được dữ liệu. Vui lòng thử lại sau.');
    } finally {
      setLoading(false);
    }
  };

  const handleTimeRangeChange = (newRange: TimeRange) => {
    setTimeRange(newRange);
    loadData(newRange);
  };

  const loadAICommentary = async (forceRefresh: boolean, range: TimeRange = timeRange) => {
    if (forceRefresh) setAiRefreshing(true);
    else setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetchAICommentary(studentId, range, forceRefresh);
      setAiData(res);
    } catch (err) {
      console.error(err);
      setAiError('Không tải được nhận xét AI. Vui lòng thử lại sau.');
    } finally {
      setAiLoading(false);
      setAiRefreshing(false);
    }
  };

  // Peer navigation within class
  const currentIndex = useMemo(() => {
    if (!classStudents || classStudents.length === 0) return -1;
    return classStudents.findIndex((s) => s.user_id === studentId);
  }, [classStudents, studentId]);

  const prevStudent = currentIndex > 0 ? classStudents[currentIndex - 1] : null;
  const nextStudent =
    currentIndex >= 0 && currentIndex < classStudents.length - 1
      ? classStudents[currentIndex + 1]
      : null;

  if (loading && !data) {
    return (
      <div className="space-y-4 p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto">
        <ErrorPanel
          title="Không thể tải dữ liệu học sinh"
          message={error ?? 'Dữ liệu hiện chưa sẵn sàng. Vui lòng thử lại.'}
          onRetry={loadData}
        />
      </div>
    );
  }

  const summary = tagData?.summary;

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      {/* Class Peer Switcher Bar (Thanh duyệt học sinh cùng lớp) */}
      {classStudents.length > 1 && (
        <div className="bg-card border border-border rounded-lg p-2.5 px-3.5 flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex items-center gap-2 text-xs min-w-0">
            <BookOpen className="w-3.5 h-3.5 text-brand-primary shrink-0" />
            <span className="text-text-secondary truncate">
              {currentClassName || 'Danh sách lớp'}
            </span>
            <span className="text-border">/</span>
            <span className="font-mono text-text-tertiary">
              Học sinh {currentIndex + 1} / {classStudents.length}
            </span>
          </div>

          <div className="flex items-center gap-1.5 ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={() => prevStudent && onSelectStudent?.(prevStudent.user_id, prevStudent.name)}
              disabled={!prevStudent}
              className="h-7 px-2 text-xs gap-1"
              title={prevStudent ? `Học sinh trước: ${prevStudent.name}` : 'Đây là học sinh đầu tiên'}
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Trước</span>
            </Button>

            {/* Quick dropdown jump to student */}
            <select
              value={studentId}
              onChange={(e) => {
                const targetId = Number(e.target.value);
                const st = classStudents.find((s) => s.user_id === targetId);
                if (st) onSelectStudent?.(st.user_id, st.name);
              }}
              aria-label="Chuyển nhanh học sinh trong lớp"
              className="h-7 rounded-sm border border-border bg-card px-2 text-xs text-text-primary cursor-pointer max-w-[150px] sm:max-w-[200px] truncate focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary"
            >
              {classStudents.map((s, idx) => (
                <option key={s.user_id} value={s.user_id}>
                  {idx + 1}. {s.name} (#{s.user_id})
                </option>
              ))}
            </select>

            <Button
              variant="outline"
              size="sm"
              onClick={() => nextStudent && onSelectStudent?.(nextStudent.user_id, nextStudent.name)}
              disabled={!nextStudent}
              className="h-7 px-2 text-xs gap-1"
              title={nextStudent ? `Học sinh kế tiếp: ${nextStudent.name}` : 'Đây là học sinh cuối cùng'}
            >
              <span className="hidden sm:inline">Sau</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Student Overview Header Card */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text-primary tracking-tight">
                {data.student_name}
              </h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                #{data.user_id}
              </Badge>
            </div>
            <p className="text-xs text-text-secondary">
              Đánh giá năng lực 8 trụ cột thuật toán, cây kỹ năng và tiến độ học tập
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <TimeRangeFilter
              value={timeRange}
              onChange={handleTimeRangeChange}
              disabled={loading}
            />
          </div>
        </CardContent>
      </Card>

      {/* Summary Telemetry Bar: Chỉ 2 cột: Bài đã giải & Lượt nộp theo mốc thời gian */}
      {summary && (
        <div className="bg-card border border-border rounded-lg p-3.5 sm:p-4 grid grid-cols-2 divide-x divide-border/60">
          <div className="px-3 sm:px-6 first:pl-2 sm:first:pl-4 flex flex-col justify-center">
            <p className="text-[11px] text-text-secondary">
              Bài đã giải{
                timeRange === '1d'
                  ? ' (1 ngày qua)'
                  : timeRange === '7d'
                  ? ' (1 tuần qua)'
                  : timeRange === '30d'
                  ? ' (1 tháng qua)'
                  : timeRange === '1y'
                  ? ' (1 năm qua)'
                  : ''
              }
            </p>
            <p className="text-xl sm:text-2xl font-bold text-text-primary font-mono mt-0.5">
              {summary.total_solved_unique}
            </p>
          </div>

          <div className="px-3 sm:px-6 flex flex-col justify-center">
            <p className="text-[11px] text-text-secondary">
              Lượt nộp{
                timeRange === '1d'
                  ? ' (1 ngày qua)'
                  : timeRange === '7d'
                  ? ' (1 tuần qua)'
                  : timeRange === '30d'
                  ? ' (1 tháng qua)'
                  : timeRange === '1y'
                  ? ' (1 năm qua)'
                  : ''
              }
            </p>
            <p className="text-xl sm:text-2xl font-bold text-text-primary font-mono mt-0.5">
              {summary.total_submissions_period ?? summary.total_submissions_7d}
            </p>
          </div>
        </div>
      )}

      {/* Bloom Radar: 1 hàng độc lập đầy chiều */}
      <div id="section-overview">
        <BloomRadar data={data.bloom_radar} />
      </div>

      {/* Cây kỹ năng */}
      <div id="section-skill-tree">
        <SkillTree nodes={data.skill_tree_nodes} />
      </div>

      {/* Tag Completion Grid */}
      <div id="section-tag-analytics">
        <TagCompletionGrid tags={tagData?.tags ?? []} />
      </div>

      {/* AI Advisor Commentary Card */}
      <AIAdvisorCard
        data={aiData}
        loading={aiLoading}
        refreshing={aiRefreshing}
        error={aiError}
        onRefresh={() => loadAICommentary(true)}
      />
    </div>
  );
};
