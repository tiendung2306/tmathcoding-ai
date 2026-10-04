import React, { useState, useMemo } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { queryClient } from '../lib/queryClient';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { studentUrl } from '../lib/navigation';
import {
  fetchSkillTree,
  fetchTagAnalytics,
  fetchAICommentary,
  requestCodeDoctor,
  fetchFailedSubmissions,
} from '../services/api';
import {
  CodeDoctorResponseData,
  ClassStudentItemData,
  TimeRange,
} from '../types';
import { BloomRadar } from '../components/BloomRadar';
import { SkillForest } from '../components/SkillForest';
import { SkillTree } from '../components/SkillTree';
import { CodeDoctorModal } from '../components/CodeDoctorModal';
import { FailedSubmissionsList } from '../components/FailedSubmissionsList';
import { AIAdvisorCard } from '../components/AIAdvisorCard';
import { TagCompletionGrid } from '../components/TagCompletionGrid';
import { TimeRangeFilter } from '../components/TimeRangeFilter';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface StudentDashboardProps {
  studentId: number;
  studentName: string;
  classStudents?: ClassStudentItemData[];
  classId?: number;
  listSearch?: string;
  rosterSearch?: string;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({
  studentId,
  studentName,
  classStudents = [],
  classId,
  listSearch = '',
  rosterSearch = '',
}) => {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const rangeValue = params.get('range') as TimeRange;
  const timeRange: TimeRange = ['1d', '7d', '30d', '1y', 'all'].includes(rangeValue) ? rangeValue : 'all';
  // Shared reads finish into their own cache, including across StrictMode remounts.
  const skill = useQuery({ queryKey: ['student', studentId, 'skill', timeRange], queryFn: () => fetchSkillTree(studentId, timeRange) });
  const tags = useQuery({ queryKey: ['student', studentId, 'tags', timeRange], queryFn: () => fetchTagAnalytics(studentId, timeRange) });
  const failed = useQuery({ queryKey: ['student', studentId, 'failed'], queryFn: () => fetchFailedSubmissions(studentId) });
  const ai = useQuery({ queryKey: ['student', studentId, 'ai', timeRange], queryFn: () => fetchAICommentary(studentId, timeRange), staleTime: 5 * 60_000 });
  const refreshAI = useMutation({
    mutationFn: (range: TimeRange) => fetchAICommentary(studentId, range, true),
    onSuccess: (result, range) => queryClient.setQueryData(['student', studentId, 'ai', range], result),
  });
  const data = skill.data;
  const tagData = tags.data;
  const [doctorModalData, setDoctorModalData] = useState<CodeDoctorResponseData | null>(null);
  const [diagnosingId, setDiagnosingId] = useState<number | null>(null);

  const handleTimeRangeChange = (newRange: TimeRange) => {
    setParams(previous => { const next = new URLSearchParams(previous); if (newRange === 'all') next.delete('range'); else next.set('range', newRange); return next; }, { preventScrollReset: true });
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

  const handleDiagnose = async (submissionId: number) => {
    setDiagnosingId(submissionId);
    try {
      const res = await requestCodeDoctor(submissionId);
      if (res.status === 'COMPLETED' && res.result?.diagnosis) {
        setDoctorModalData(res.result);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDiagnosingId(null);
    }
  };

  const summary = tagData?.summary;

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      {classId && classStudents.length > 1 && <nav aria-label="Học sinh trong lớp" className="bg-card border border-border rounded-lg p-3 flex flex-wrap items-center gap-3">
        <span className="text-sm text-text-secondary">Chuyển học sinh trong lớp</span>
        <div className="flex w-full sm:w-auto items-center gap-2 sm:ml-auto min-w-0">
          {prevStudent ? <Link to={studentUrl(prevStudent.user_id, classId, listSearch, rosterSearch, timeRange)} aria-label={`Học sinh trước: ${prevStudent.name}`} className="h-11 min-w-11 px-2 inline-flex justify-center items-center gap-1 text-sm border border-border-control rounded-md"><ChevronLeft className="w-4 h-4" /><span className="hidden sm:inline">Trước</span></Link> : <button disabled aria-label="Đây là học sinh đầu tiên" className="h-11 min-w-11 px-2 inline-flex justify-center items-center gap-1 text-sm border border-border-control rounded-md text-text-secondary opacity-50"><ChevronLeft className="w-4 h-4" /><span className="hidden sm:inline">Trước</span></button>}
          <select value={studentId} onChange={event => navigate(studentUrl(Number(event.target.value), classId, listSearch, rosterSearch, timeRange))} aria-label="Chuyển nhanh học sinh trong lớp" className="h-11 min-w-0 flex-1 sm:max-w-60 rounded-md border border-border-control bg-card px-2 text-sm">
            {classStudents.map((student, index) => <option key={student.user_id} value={student.user_id}>{index + 1}. {student.name}</option>)}
          </select>
          {nextStudent ? <Link to={studentUrl(nextStudent.user_id, classId, listSearch, rosterSearch, timeRange)} aria-label={`Học sinh kế tiếp: ${nextStudent.name}`} className="h-11 min-w-11 px-2 inline-flex justify-center items-center gap-1 text-sm border border-border-control rounded-md"><span className="hidden sm:inline">Sau</span><ChevronRight className="w-4 h-4" /></Link> : <button disabled aria-label="Đây là học sinh cuối cùng" className="h-11 min-w-11 px-2 inline-flex justify-center items-center gap-1 text-sm border border-border-control rounded-md text-text-secondary opacity-50"><span className="hidden sm:inline">Sau</span><ChevronRight className="w-4 h-4" /></button>}
        </div>
      </nav>}

      {/* Student Overview Header Card */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text-primary tracking-tight">
                {studentName}
              </h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                #{studentId}
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <TimeRangeFilter
              value={timeRange}
              onChange={handleTimeRangeChange}
            />
          </div>
        </CardContent>
      </Card>

      {/* Summary Telemetry Bar: Chỉ 2 cột: Bài đã giải & Lượt nộp theo mốc thời gian */}
      {tags.isPending && <SectionLoading label="Đang tải thống kê bài làm..." />}
      {tags.isError && <ErrorPanel title="Không tải được phân tích chuyên đề" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void tags.refetch({ cancelRefetch: false }); }} />}
      {summary && (
        <div className="bg-card border border-border rounded-lg p-3.5 sm:p-4 grid grid-cols-2 divide-x divide-border/60">
          <div className="px-3 sm:px-6 first:pl-2 sm:first:pl-4 flex flex-col justify-center">
            <p className="text-[11px] text-text-secondary">
              Bài đã AC{
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
      {skill.isPending && <SectionLoading label="Đang tải năng lực và cây kỹ năng..." />}
      {skill.isError && <ErrorPanel title="Không tải được sơ đồ kỹ năng" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void skill.refetch({ cancelRefetch: false }); }} />}
      {data && <>{!data.skill_forest && <div id="section-overview">
        <BloomRadar data={data.bloom_radar} />
      </div>}

      {/* Cây kỹ năng */}
      <div id="section-skill-tree">
        {data.skill_forest ? <SkillForest roots={data.skill_forest} userId={studentId} timeRange={timeRange} /> : <SkillTree nodes={data.skill_tree_nodes} />}
      </div></>}

      {/* Failed Submissions (Code Doctor Selection) */}
      <div id="section-failed-submissions">
        {failed.isError ? <ErrorPanel title="Không tải được bài nộp lỗi" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void failed.refetch({ cancelRefetch: false }); }} /> :
        <FailedSubmissionsList
          submissions={failed.data ?? []}
          loading={failed.isPending}
          onDiagnose={handleDiagnose}
          diagnosingId={diagnosingId}
        />}
      </div>

      {/* Tag Completion Grid */}
      {tagData && <div id="section-tag-analytics">
        {data?.skill_forest ? <details className="skill-panel"><summary className="cursor-pointer px-4 py-3 min-h-11 font-medium">Phân tích lượt nộp theo dạng bài</summary><div className="p-4 border-t border-border"><TagCompletionGrid tags={tagData.tags} countsOnly /></div></details> : <TagCompletionGrid tags={tagData.tags} />}
      </div>}

      {/* AI Advisor Commentary Card */}
      <AIAdvisorCard
        data={ai.data ?? null}
        loading={ai.isPending}
        refreshing={refreshAI.isPending || (ai.isFetching && !ai.isPending)}
        error={ai.isError || (refreshAI.isError && refreshAI.variables === timeRange) ? 'Không tải được nhận xét AI. Hãy thử lại.' : null}
        onRefresh={() => { if (ai.isError) void ai.refetch({ cancelRefetch: false }); else refreshAI.mutate(timeRange); }}
      />

      {/* Code Doctor Modal */}
      {doctorModalData && (
        <CodeDoctorModal
          data={doctorModalData}
          onClose={() => setDoctorModalData(null)}
        />
      )}
    </div>
  );
};

function SectionLoading({ label }: { label: string }) {
  return <div className="space-y-3 rounded-lg border border-border bg-card p-4" aria-busy="true">
    <p role="status" className="text-sm text-text-secondary">{label}</p>
    <Skeleton className="h-24 w-full" />
  </div>;
}
