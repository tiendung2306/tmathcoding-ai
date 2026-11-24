import React, { lazy, Suspense, useEffect } from 'react';
import axios from 'axios';
import { apiClient } from './lib/apiClient';
import { createBrowserRouter, Link, isRouteErrorResponse, redirect, useLoaderData, useLocation, useRevalidator, useRouteError, useSearchParams } from 'react-router-dom';
import App, { PageHandle } from './App';
import { LoginPage } from './pages/LoginPage';
import { getAccount, type AuthAccount } from './services/auth';
import { ClassStudentsGrid } from './components/ClassStudentsGrid';
import { StudentsPage } from './pages/StudentsPage';
import { TeacherHome } from './pages/TeacherHome';
import { ContestsPage } from './pages/ContestsPage';
import { ContestRoomPage } from './pages/ContestRoomPage';
import { ClassStudentItemData } from './types';
import { positiveId, studentUrl } from './lib/navigation';
import { ClassContext, loadClass, loadContest, loadProfile, loadRoster, routeRequest } from './services/navigation';

const StudentDashboard = lazy(() => import('./pages/StudentDashboard').then(module => ({ default: module.StudentDashboard })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(module => ({ default: module.AdminDashboard })));
const SkillConfiguration = lazy(() => import('./pages/SkillConfiguration').then(module => ({ default: module.SkillConfiguration })));
const pageLoading = <p role="status" className="p-5 text-sm text-text-secondary">Đang mở trang...</p>;

function RouteError() {
  const error = useRouteError();
  const revalidator = useRevalidator();
  const { pathname } = useLocation();
  const status = isRouteErrorResponse(error) ? error.status : 503;
  const unavailable = status === 404;
  const forbidden = status === 401 || status === 403;
  const title = unavailable ? 'Không tìm thấy trang' : forbidden ? 'Không thể truy cập' : 'Không tải được trang';
  useEffect(() => { document.title = `${title} · tmath`; }, [title]);
  return <section className="max-w-3xl mx-auto p-5 sm:p-8" aria-labelledby="route-error-title">
    <h1 id="route-error-title" tabIndex={-1} ref={node => node?.focus({ preventScroll: true })} className="text-xl font-semibold">{title}</h1>
    <p role="alert" className="mt-3 text-text-secondary">{unavailable ? 'Địa chỉ không hợp lệ hoặc dữ liệu không còn trong danh sách được phép xem.' : status === 401 ? 'Phiên đăng nhập đã hết hạn.' : forbidden ? 'Bạn không có quyền xem dữ liệu này.' : 'Không thể kết nối để tải dữ liệu. Hãy thử lại.'}</p>
    <div className="mt-5 flex flex-wrap gap-3">
      {status === 401 && <Link to={`/login?next=${encodeURIComponent(pathname)}`} className="skill-primary">Đăng nhập</Link>}
      {!unavailable && !forbidden && <button disabled={revalidator.state !== 'idle'} onClick={() => revalidator.revalidate()} className="min-h-11 px-4 rounded-md bg-brand-primary text-white">{revalidator.state !== 'idle' ? 'Đang thử lại...' : 'Thử lại'}</button>}
      <Link to={pathname.startsWith('/teacher') ? '/teacher/contests' : '/student/students'} className="min-h-11 px-4 inline-flex items-center rounded-md border border-border">Về danh sách</Link>
      <Link to="/teacher/home" className="min-h-11 px-3 inline-flex items-center underline">Về trang chủ</Link>
    </div>
  </section>;
}

interface RosterData { organization: ClassContext; students: ClassStudentItemData[] }
interface StudentData { id: number; name: string; organization: ClassContext | null; students: ClassStudentItemData[] }
function RosterPage() {
  const { organization, students } = useLoaderData() as RosterData;
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const list = params.get('list') || '';
  const roster = new URLSearchParams(params); roster.delete('list');
  return <ClassStudentsGrid classNameTitle={organization.name} classId={organization.id} students={students} loading={false} studentHref={id => studentUrl(id, organization.id, list, roster.toString())} />;
}
function StudentPage() {
  const data = useLoaderData() as StudentData;
  const currentStudent = data.students.find(student => student.user_id === data.id);
  return <Suspense fallback={pageLoading}><StudentDashboard key={data.id} studentId={data.id} studentName={data.name} avatarUrl={currentStudent?.avatar_url ?? null} /></Suspense>;
}
async function requireReadyAccount(request: Request): Promise<AuthAccount> {
  let account: AuthAccount;
  try {
    account = await getAccount();
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = new URL(request.url);
      throw redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`);
    }
    throw error;
  }
  return account;
}

async function guardedRouteRequest<T>(request: Request, load: () => Promise<T>): Promise<T> {
  await requireReadyAccount(request);
  return routeRequest(load);
}

const studentsLoader = ({ request }: { request: Request }) => guardedRouteRequest(request, async () => {
  const params = new URL(request.url).searchParams;
  const page = Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1);
  const requestedSort = params.get('sort');
  const sort = requestedSort === 'name' || requestedSort === 'name_desc' || requestedSort === 'points_asc' ? requestedSort : 'points_desc';
  return (await apiClient.get('/api/v1/teacher/my-students', { params: { page, q: (params.get('q') || '').trim().slice(0, 128), sort }, signal: request.signal })).data;
});
export const router = createBrowserRouter([
  { path: '/', loader: () => redirect('/teacher/home'), errorElement: <RouteError /> },
  { path: '/login', loader: async () => {
      try {
        await getAccount();
        return redirect('/teacher/home');
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 401) return null;
        throw error;
      }
    }, element: <LoginPage />, errorElement: <RouteError /> },
  { path: '/settings', loader: () => redirect('/student/students') },
  { id: 'app', loader: ({ request }) => requireReadyAccount(request), element: <App />, errorElement: <RouteError />, children: [
    { path: '/teacher/home', element: <TeacherHome />, handle: { title: 'Trang chủ' } satisfies PageHandle },
    { path: '/teacher/contests', element: <ContestsPage />, errorElement: <RouteError />, handle: { title: 'Cuộc thi' } satisfies PageHandle },
    { path: '/teacher/contests/:contestId', element: <ContestRoomPage />, errorElement: <RouteError />,
      loader: ({ params, request }) => guardedRouteRequest(request, () => loadContest(positiveId(params.contestId), request.signal)),
      handle: { title: data => data?.title || 'Phòng cuộc thi' } satisfies PageHandle },
    { path: '/teacher/classes', loader: () => redirect('/teacher/contests') },
    { path: '/student/classes', loader: () => redirect('/student/students') },
    { path: '/student/students', loader: studentsLoader, element: <StudentsPage />, errorElement: <RouteError />, handle: { title: 'Học sinh' } satisfies PageHandle },
    { path: '/student/classes/:classId/students', element: <RosterPage />, errorElement: <RouteError />,
      shouldRevalidate: ({ currentParams, nextParams, defaultShouldRevalidate, currentUrl, nextUrl }) => currentParams.classId !== nextParams.classId || (currentUrl.search === nextUrl.search && defaultShouldRevalidate),
      loader: ({ params, request }) => guardedRouteRequest(request, async () => {
        const id = positiveId(params.classId);
        const [organization, students] = await Promise.all([loadClass(id, request.signal), loadRoster(id, request.signal)]);
        return { organization, students };
      }),
      handle: { title: data => data?.organization?.name || 'Học sinh trong lớp' } satisfies PageHandle },
    { path: '/student/students/:studentId', element: <StudentPage />, errorElement: <RouteError />,
      shouldRevalidate: ({ currentParams, nextParams, currentUrl, nextUrl, defaultShouldRevalidate }) => currentParams.studentId !== nextParams.studentId || currentUrl.searchParams.get('class') !== nextUrl.searchParams.get('class') || (currentUrl.search === nextUrl.search && defaultShouldRevalidate),
      loader: ({ params, request }) => guardedRouteRequest(request, async () => {
        const id = positiveId(params.studentId);
        const search = new URL(request.url).searchParams;
        if (!search.has('class')) return { ...await loadProfile(id, request.signal), organization: null, students: [] };
        const classId = positiveId(search.get('class'));
        const [organization, students] = await Promise.all([loadClass(classId, request.signal), loadRoster(classId, request.signal)]);
        const student = students.find(student => student.user_id === id);
        if (!student) throw new Response('Học sinh không thuộc lớp này.', { status: 404 });
        return { id, name: student.name, organization, students };
      }),
      handle: { title: data => data?.name || 'Học sinh' } satisfies PageHandle },
    // Old session URLs: sessions are Source API contests now.
    { path: '/teacher/classes/:classId/sessions', loader: () => redirect('/teacher/contests') },
    { path: '/teacher/sessions/:sessionId', loader: () => redirect('/teacher/contests') },
    { path: '/admin', element: <Suspense fallback={pageLoading}><AdminDashboard /></Suspense>, errorElement: <RouteError />, handle: { title: 'Quản trị gắn tag' } satisfies PageHandle },
    { path: '/admin/skills', element: <Suspense fallback={pageLoading}><SkillConfiguration /></Suspense>, errorElement: <RouteError />, handle: { title: 'Cấu hình cây kỹ năng' } satisfies PageHandle },
    { path: '/admin/scoring', loader: () => redirect('/student/students') },
    { path: '*', loader: () => { throw new Response('Không tìm thấy trang.', { status: 404 }); }, errorElement: <RouteError /> },
  ] },
]);
