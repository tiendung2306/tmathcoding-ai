import React, { lazy, Suspense, useCallback, useEffect, useMemo } from 'react';
import axios from 'axios';
import { createBrowserRouter, Link, isRouteErrorResponse, useLoaderData, useLocation, useNavigate, useRevalidator, useRouteError, useSearchParams } from 'react-router-dom';
import App, { PageHandle } from './App';
import { RoleSelect } from './components/RoleSelect';
import { ClassTable } from './components/ClassTable';
import { ClassStudentsGrid } from './components/ClassStudentsGrid';
import { VirtualClassSessions } from './components/VirtualClassSessions';
import { ClassListQuery, ClassStudentItemData, ClassPageData } from './types';
import { classListUrl, classQuery, classSearch, positiveId, rosterUrl, studentUrl } from './lib/navigation';
import { ClassContext, loadClass, loadProfile, loadRoster, loadSession, routeRequest, SessionDetail } from './services/navigation';

const StudentDashboard = lazy(() => import('./pages/StudentDashboard').then(module => ({ default: module.StudentDashboard })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(module => ({ default: module.AdminDashboard })));
const VirtualClassLiveRoom = lazy(() => import('./pages/VirtualClassLiveRoom').then(module => ({ default: module.VirtualClassLiveRoom })));
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
    <p role="alert" className="mt-3 text-text-secondary">{unavailable ? 'Địa chỉ không hợp lệ hoặc dữ liệu không còn trong danh sách được phép xem.' : forbidden ? 'Bạn không có quyền xem dữ liệu này.' : 'Không thể kết nối để tải dữ liệu. Hãy thử lại.'}</p>
    <div className="mt-5 flex flex-wrap gap-3">
      {!unavailable && !forbidden && <button disabled={revalidator.state !== 'idle'} onClick={() => revalidator.revalidate()} className="min-h-11 px-4 rounded-md bg-brand-primary text-white">{revalidator.state !== 'idle' ? 'Đang thử lại...' : 'Thử lại'}</button>}
      <Link to={pathname.startsWith('/teacher') ? '/teacher/classes' : '/student/classes'} className="min-h-11 px-4 inline-flex items-center rounded-md border border-border">Về danh sách lớp</Link>
      <Link to="/" className="min-h-11 px-3 inline-flex items-center underline">Chọn khu vực</Link>
    </div>
  </section>;
}

function ClassesPage({ area }: { area: 'student' | 'teacher' }) {
  const [params, setParams] = useSearchParams();
  const initialData = useLoaderData() as ClassPageData;
  const query = useMemo(() => classQuery(params), [params]);
  const canonical = classSearch(query);
  useEffect(() => { if (params.toString() !== canonical) setParams(canonical, { replace: true }); }, [canonical, params, setParams]);
  const update = useCallback((next: ClassListQuery, options?: { replace?: boolean }) => {
    const current = classQuery(new URLSearchParams(window.location.search));
    setParams(classSearch(next), { replace: options?.replace ?? next.q !== current.q, preventScrollReset: next.q !== current.q });
  }, [setParams]);
  const classHref = (id: number) => {
    if (area === 'student') return rosterUrl(id, canonical);
    const search = canonical ? `?${new URLSearchParams({ list: canonical })}` : '';
    return `/teacher/classes/${id}/sessions${search}`;
  };
  return <ClassTable query={query} onQueryChange={update} classHref={classHref} initialData={initialData} />;
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
  const [params] = useSearchParams();
  return <Suspense fallback={pageLoading}><StudentDashboard key={data.id} studentId={data.id} studentName={data.name} classStudents={data.students} classId={data.organization?.id} listSearch={params.get('list') || ''} rosterSearch={params.get('roster') || ''} /></Suspense>;
}
function SessionsPage() {
  const data = useLoaderData() as ClassContext;
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const suffix = params.get('list') ? `?${new URLSearchParams({ list: params.get('list')! })}` : '';
  return <VirtualClassSessions key={data.id} selectedOrgId={data.id} className={data.name} sessionHref={id => `/teacher/sessions/${id}${suffix}`} onEnterSession={id => navigate(`/teacher/sessions/${id}${suffix}`)} />;
}
function SessionPage() {
  const data = useLoaderData() as SessionDetail;
  const revalidator = useRevalidator();
  return <Suspense fallback={pageLoading}><VirtualClassLiveRoom key={data.id} sessionId={data.id} sessionName={data.name} isActive={data.end_time === null} onSessionStopped={() => revalidator.revalidate()} /></Suspense>;
}

const classCrumb = (area: 'student' | 'teacher', search: URLSearchParams) => ({ label: 'Danh sách lớp', to: classListUrl(area, search.get('list') || '') });
const classesLoader = ({ request }: { request: Request }) => routeRequest(async () => (await axios.get('/api/v1/teacher/my-classes', { params: classQuery(new URL(request.url).searchParams), signal: request.signal })).data);
export const router = createBrowserRouter([
  { path: '/', element: <RoleSelect />, errorElement: <RouteError /> },
  { element: <App />, errorElement: <RouteError />, children: [
    { path: '/student/classes', loader: classesLoader, element: <ClassesPage area="student" />, errorElement: <RouteError />, handle: { title: 'Danh sách lớp' } satisfies PageHandle },
    { path: '/teacher/classes', loader: classesLoader, element: <ClassesPage area="teacher" />, errorElement: <RouteError />, handle: { title: 'Lớp học ảo' } satisfies PageHandle },
    { path: '/student/classes/:classId/students', element: <RosterPage />, errorElement: <RouteError />,
      shouldRevalidate: ({ currentParams, nextParams, defaultShouldRevalidate, currentUrl, nextUrl }) => currentParams.classId !== nextParams.classId || (currentUrl.search === nextUrl.search && defaultShouldRevalidate),
      loader: ({ params, request }) => routeRequest(async () => {
        const id = positiveId(params.classId);
        const [organization, students] = await Promise.all([loadClass(id, request.signal), loadRoster(id, request.signal)]);
        return { organization, students };
      }),
      handle: { title: data => data?.organization?.name || 'Học sinh trong lớp', crumbs: (data, search) => [classCrumb('student', search), { label: data?.organization?.name || 'Học sinh trong lớp' }] } satisfies PageHandle },
    { path: '/student/students/:studentId', element: <StudentPage />, errorElement: <RouteError />,
      shouldRevalidate: ({ currentParams, nextParams, currentUrl, nextUrl, defaultShouldRevalidate }) => currentParams.studentId !== nextParams.studentId || currentUrl.searchParams.get('class') !== nextUrl.searchParams.get('class') || (currentUrl.search === nextUrl.search && defaultShouldRevalidate),
      loader: ({ params, request }) => routeRequest(async () => {
        const id = positiveId(params.studentId);
        const search = new URL(request.url).searchParams;
        if (!search.has('class')) return { ...await loadProfile(id, request.signal), organization: null, students: [] };
        const classId = positiveId(search.get('class'));
        const [organization, students] = await Promise.all([loadClass(classId, request.signal), loadRoster(classId, request.signal)]);
        const student = students.find(student => student.user_id === id);
        if (!student) throw new Response('Học sinh không thuộc lớp này.', { status: 404 });
        return { id, name: student.name, organization, students };
      }),
      handle: { title: data => data?.name || 'Học sinh', crumbs: (data, search) => [classCrumb('student', search), ...(data?.organization ? [{ label: data.organization.name, to: rosterUrl(data.organization.id, search.get('list') || '', search.get('roster') || '') }] : []), { label: data?.name || 'Học sinh' }] } satisfies PageHandle },
    { path: '/teacher/classes/:classId/sessions', element: <SessionsPage />, errorElement: <RouteError />,
      loader: ({ params, request }) => routeRequest(() => loadClass(positiveId(params.classId), request.signal)),
      handle: { title: data => data?.name || 'Phiên học', crumbs: (data, search) => [classCrumb('teacher', search), { label: data?.name || 'Phiên học' }] } satisfies PageHandle },
    { path: '/teacher/sessions/:sessionId', element: <SessionPage />, errorElement: <RouteError />,
      loader: ({ params, request }) => routeRequest(() => loadSession(positiveId(params.sessionId), request.signal)),
      handle: { title: data => data?.name || 'Phiên học', crumbs: (data, search) => [classCrumb('teacher', search), { label: data?.class_name || 'Lớp học', to: `/teacher/classes/${data?.org_id}/sessions${search.get('list') ? `?${new URLSearchParams({ list: search.get('list')! })}` : ''}` }, { label: data?.name || 'Phiên học' }] } satisfies PageHandle },
    { path: '/admin', element: <Suspense fallback={pageLoading}><AdminDashboard /></Suspense>, errorElement: <RouteError />, handle: { title: 'Quản trị gắn tag' } satisfies PageHandle },
    { path: '*', loader: () => { throw new Response('Không tìm thấy trang.', { status: 404 }); }, errorElement: <RouteError /> },
  ] },
]);
