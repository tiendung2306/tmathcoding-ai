import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { queryClient } from '../lib/queryClient';
import { fetchAICommentary, fetchFailedSubmissions, fetchSkillTree, fetchTagAnalytics, requestCodeDoctor } from '../services/api';
import { CodeDoctorResponseData, TimeRange } from '../types';
import { BloomRadar } from '../components/BloomRadar';
import { SkillForest } from '../components/SkillForest';
import { SkillTree } from '../components/SkillTree';
import { CodeDoctorModal } from '../components/CodeDoctorModal';
import { FailedSubmissionsList } from '../components/FailedSubmissionsList';
import { AIAdvisorCard } from '../components/AIAdvisorCard';
import { TimeRangeFilter } from '../components/TimeRangeFilter';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { ChevronLeft } from 'lucide-react';

interface StudentDashboardProps {
  studentId: number;
  studentName: string;
  avatarUrl: string | null;
  backTo?: string;
  className?: string;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ studentId, studentName, avatarUrl, backTo, className }) => {
  const [params, setParams] = useSearchParams();
  const rangeValue = params.get('range') as TimeRange;
  const timeRange: TimeRange = ['1d', '7d', '30d', '1y', 'all'].includes(rangeValue) ? rangeValue : 'all';
  const activeTab = params.get('tab') === 'submissions' ? 'submissions' : 'overview';
  const skill = useQuery({ queryKey: ['student', studentId, 'skill', timeRange], queryFn: () => fetchSkillTree(studentId, timeRange) });
  const tags = useQuery({ queryKey: ['student', studentId, 'tags', timeRange], queryFn: () => fetchTagAnalytics(studentId, timeRange) });
  const failed = useQuery({ queryKey: ['student', studentId, 'failed'], queryFn: () => fetchFailedSubmissions(studentId) });
  const ai = useQuery({ queryKey: ['student', studentId, 'ai', timeRange], queryFn: () => fetchAICommentary(studentId, timeRange), staleTime: 5 * 60_000 });
  const generateAI = useMutation({
    mutationFn: (range: TimeRange) => fetchAICommentary(studentId, range, true),
    onSuccess: (result, range) => queryClient.setQueryData(['student', studentId, 'ai', range], result),
  });
  const [doctorModalData, setDoctorModalData] = useState<CodeDoctorResponseData | null>(null);
  const [diagnosingId, setDiagnosingId] = useState<number | null>(null);
  const summary = tags.data?.summary;

  const updateParams = (update: (next: URLSearchParams) => void) => {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      update(next);
      return next;
    }, { preventScrollReset: true });
  };

  const handleTimeRangeChange = (newRange: TimeRange) => {
    updateParams(next => {
      if (newRange === 'all') next.delete('range'); else next.set('range', newRange);
    });
  };

  const handleDiagnose = async (submissionId: number) => {
    setDiagnosingId(submissionId);
    try {
      const response = await requestCodeDoctor(submissionId);
      if (response.status === 'COMPLETED' && response.result?.diagnosis) setDoctorModalData(response.result);
    } catch (error) {
      console.error(error);
    } finally {
      setDiagnosingId(null);
    }
  };

  return <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
    {backTo && className && <Link to={backTo} className="student-back-link">
      <ChevronLeft aria-hidden className="h-4 w-4" />
      <span>Quay về lớp {className}</span>
    </Link>}
    <Card className="bg-card border-border">
      <CardContent className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <StudentAvatar avatarUrl={avatarUrl} name={studentName} />
          <h1 className="truncate text-xl font-bold text-text-primary tracking-tight">{studentName}</h1>
          <Badge variant="outline" className="text-[10px] font-mono">#{studentId}</Badge>
        </div>
        <TimeRangeFilter value={timeRange} onChange={handleTimeRangeChange} />
        </div>
        <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-[minmax(0,1fr)_15rem] lg:items-start">
          <AIAdvisorCard
            data={ai.data ?? null}
            loading={ai.isPending}
            generating={generateAI.isPending}
            error={ai.isError || (generateAI.isError && generateAI.variables === timeRange) ? 'Không tải được nhận xét AI. Hãy thử lại.' : null}
            onGenerate={() => { if (ai.isError) void ai.refetch({ cancelRefetch: false }); else generateAI.mutate(timeRange); }}
          />
          <div className="grid grid-cols-2 divide-x divide-border border-t border-border pt-3 lg:border-l lg:border-t-0 lg:pt-0">
            {tags.isPending ? <p role="status" className="col-span-2 text-xs text-text-secondary">Đang tải thống kê...</p> : summary ? <>
              <Statistic label="Bài đã AC" value={summary.total_solved_unique} />
              <Statistic label="Lượt nộp" value={summary.total_submissions_period ?? summary.total_submissions_7d} />
            </> : null}
          </div>
        </div>
      </CardContent>
    </Card>
    {tags.isError && <ErrorPanel title="Không tải được thống kê" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void tags.refetch({ cancelRefetch: false }); }} />}

    {activeTab === 'overview' ? <div role="tabpanel" className="space-y-4">
      {skill.isPending && <SectionLoading label="Đang tải năng lực và cây kỹ năng..." />}
      {skill.isError && <ErrorPanel title="Không tải được sơ đồ kỹ năng" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void skill.refetch({ cancelRefetch: false }); }} />}
      {skill.data && <>
        <div id="section-overview"><BloomRadar data={skill.data.bloom_radar} /></div>
        <div id="section-skill-tree">{skill.data.skill_forest ? <SkillForest roots={skill.data.skill_forest} userId={studentId} timeRange={timeRange} /> : <SkillTree nodes={skill.data.skill_tree_nodes} />}</div>
      </>}
    </div> : <div role="tabpanel" id="section-failed-submissions">
      {failed.isError ? <ErrorPanel title="Không tải được bài nộp chưa đạt" message="Hãy thử tải lại phần dữ liệu này." onRetry={() => { void failed.refetch({ cancelRefetch: false }); }} /> : <FailedSubmissionsList submissions={failed.data ?? []} loading={failed.isPending} onDiagnose={handleDiagnose} diagnosingId={diagnosingId} />}
    </div>}

    {doctorModalData && <CodeDoctorModal data={doctorModalData} onClose={() => setDoctorModalData(null)} />}
  </div>;
};

function Statistic({ label, value }: { label: string; value: number }) {
  return <div className="px-3 sm:px-6 first:pl-2 sm:first:pl-4 flex flex-col justify-center">
    <p className="text-[11px] text-text-secondary">{label}</p>
    <p className="text-xl sm:text-2xl font-bold text-text-primary font-mono mt-0.5">{value}</p>
  </div>;
}

function StudentAvatar({ avatarUrl, name }: { avatarUrl: string | null; name: string }) {
  const initials = name.trim().split(/\s+/).slice(-2).map(part => part[0]).join('').toUpperCase() || '?';
  return avatarUrl ? <img src={avatarUrl} alt="" className="h-10 w-10 shrink-0 rounded-full border border-border object-cover" /> : <span aria-hidden className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-primary/10 text-xs font-semibold text-brand-primary">{initials}</span>;
}

function SectionLoading({ label }: { label: string }) {
  return <div className="space-y-3 rounded-lg border border-border bg-card p-4" aria-busy="true">
    <p role="status" className="text-sm text-text-secondary">{label}</p>
    <Skeleton className="h-24 w-full" />
  </div>;
}
