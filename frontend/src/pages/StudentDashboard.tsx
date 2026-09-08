import React, { useEffect, useState } from 'react';
import { fetchSkillTree, fetchTagAnalytics, fetchAICommentary, requestCodeDoctor, fetchFailedSubmissions } from '../services/api';
import { SkillTreeResponseData, CodeDoctorResponseData, TagAnalyticsResponseData, AICommentaryResponseData, FailedSubmissionItem } from '../types';
import { BloomRadar } from '../components/BloomRadar';
import { SkillTree } from '../components/SkillTree';
import { CodeDoctorModal } from '../components/CodeDoctorModal';
import { FailedSubmissionsList } from '../components/FailedSubmissionsList';
import { AIAdvisorCard } from '../components/AIAdvisorCard';
import { TagCompletionGrid } from '../components/TagCompletionGrid';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Stethoscope, BookOpen, Trophy, Activity, User } from 'lucide-react';

interface StudentDashboardProps {
  studentId: number;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ studentId }) => {
  const [data, setData] = useState<SkillTreeResponseData | null>(null);
  const [tagData, setTagData] = useState<TagAnalyticsResponseData | null>(null);
  const [aiData, setAiData] = useState<AICommentaryResponseData | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(true);
  const [aiRefreshing, setAiRefreshing] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [doctorModalData, setDoctorModalData] = useState<CodeDoctorResponseData | null>(null);
  const [failedSubmissions, setFailedSubmissions] = useState<FailedSubmissionItem[]>([]);
  const [diagnosingId, setDiagnosingId] = useState<number | null>(null);

  useEffect(() => {
    loadData();
  }, [studentId]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    loadAICommentary(false);
    try {
      const [skillRes, tagRes, failedRes] = await Promise.allSettled([
        fetchSkillTree(studentId),
        fetchTagAnalytics(studentId),
        fetchFailedSubmissions(studentId),
      ]);
      if (skillRes.status === 'fulfilled') {
        setData(skillRes.value);
      } else {
        setError('Không tải được sơ đồ kỹ năng của học sinh. Vui lòng thử lại sau.');
      }
      if (tagRes.status === 'fulfilled') setTagData(tagRes.value);
      if (failedRes.status === 'fulfilled') setFailedSubmissions(failedRes.value);
    } catch (err) {
      console.error(err);
      setError('Không tải được dữ liệu. Vui lòng thử lại sau.');
    } finally {
      setLoading(false);
    }
  };

  const loadAICommentary = async (forceRefresh: boolean) => {
    if (forceRefresh) setAiRefreshing(true);
    else setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetchAICommentary(studentId, forceRefresh);
      setAiData(res);
    } catch (err) {
      console.error(err);
      setAiError('Không tải được nhận xét AI. Vui lòng thử lại sau.');
    } finally {
      setAiLoading(false);
      setAiRefreshing(false);
    }
  };

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

  if (loading && !data) {
    return (
      <div className="space-y-5 p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-16 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 lg:col-span-2 w-full" />
        </div>
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
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-5">
      {/* Student Overview Header Card */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
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
              Học sinh tmath OJ
            </p>
          </div>

          <div className="flex items-center gap-3">
            {failedSubmissions.length > 0 ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const el = document.getElementById('section-failed-submissions');
                  el?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="gap-2 h-8 px-3 text-xs font-medium border-red-200 text-red-700 bg-red-50 hover:bg-red-100"
              >
                <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                <span>{failedSubmissions.length} bài cần chẩn đoán</span>
              </Button>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-text-secondary">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                <span>Không có bài nộp lỗi</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Telemetry Bar */}
      {summary && (
        <div className="bg-card border border-border rounded-lg p-3.5 sm:p-4 grid grid-cols-2 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border/60 gap-3 sm:gap-0">
          <div className="sm:px-4 first:pl-0 flex flex-col justify-center">
            <p className="text-[11px] text-text-secondary">Bài đã giải</p>
            <p className="text-xl font-bold text-text-primary font-mono mt-0.5">
              {summary.total_solved_unique}
            </p>
          </div>

          <div className="pt-2 sm:pt-0 sm:px-4 flex flex-col justify-center">
            <p className="text-[11px] text-text-secondary">Lượt nộp 7 ngày qua</p>
            <p className="text-xl font-bold text-text-primary font-mono mt-0.5">
              {summary.total_submissions_7d}
            </p>
          </div>

          <div className="pt-2 sm:pt-0 sm:px-4 last:pr-0 flex flex-col justify-center col-span-2 sm:col-span-1">
            <p className="text-[11px] text-text-secondary">Dạng bài theo dõi</p>
            <p className="text-xl font-bold text-text-primary font-mono mt-0.5">
              {tagData?.tags.length ?? 0}
            </p>
          </div>
        </div>
      )}

      {/* Main Grid: Bloom Radar + Skill Tree */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div id="section-overview" className="lg:col-span-1">
          <BloomRadar data={data.bloom_radar} />
        </div>
        <div id="section-skill-tree" className="lg:col-span-2">
          <SkillTree nodes={data.skill_tree_nodes} />
        </div>
      </div>

      {/* Failed Submissions (Code Doctor Selection) */}
      <div id="section-failed-submissions">
        <FailedSubmissionsList
          submissions={failedSubmissions}
          loading={loading}
          onDiagnose={handleDiagnose}
          diagnosingId={diagnosingId}
        />
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

      {/* Code Doctor Modal */}
      <CodeDoctorModal data={doctorModalData} onClose={() => setDoctorModalData(null)} />
    </div>
  );
};
