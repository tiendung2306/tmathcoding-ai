import asyncio
from fastapi import APIRouter, Depends, HTTPException

from app.core.dashboard_database import get_dashboard_db
from app.core.dashboard_auth import require_admin
from app.schemas.admin import (
    AutoTagStatusResponse,
    AutoTagBatchRunRequest,
    AutoTagBatchRunResponse
)
from app.services.auto_tag_service import auto_tag_service
from app.services.source_gateway import SourceGateway, get_source_gateway

router = APIRouter(dependencies=[Depends(require_admin)])

# Giữ tham chiếu tới task nền để GC không thu hồi task đang chạy
_bg_tasks: set = set()


@router.post("/auto-tag/run-batch", response_model=AutoTagBatchRunResponse)
async def run_auto_tagging_batch(payload: AutoTagBatchRunRequest = AutoTagBatchRunRequest(),
                                 admin=Depends(require_admin),
                                 source: SourceGateway = Depends(get_source_gateway)):
    """
    Kích hoạt tiến trình chạy batch Auto-Tagging trong nền cho các bài toán chưa gắn nhãn.
    Có giới hạn tốc độ (rate limit) và kiểm tra chống chạy trùng lặp.
    """
    # Kiểm tra is_running là check-then-act nên vẫn có race nếu 2 request đến cùng lúc;
    # chấp nhận cho tool admin đơn người vì run_batch_process tự bỏ qua nếu worker đang chạy.
    if auto_tag_service.is_running:
        raise HTTPException(
            status_code=409,
            detail="Tiến trình gắn nhãn tự động đang chạy. Vui lòng chờ hoàn thành trước khi bắt đầu đợt mới."
        )

    # asyncio.create_task thay BackgroundTasks: task tách khỏi vòng đời request,
    # client disconnect hay request bị hủy không ảnh hưởng pipeline đang chạy.
    task = asyncio.create_task(auto_tag_service.run_batch_process(
        source, actor_profile_id=admin.source_profile_id, batch_size=payload.batch_size,
    ))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

    return AutoTagBatchRunResponse(
        status="started",
        message=f"Đã kích hoạt tiến trình gắn nhãn tự động cho {payload.batch_size} bài toán trong nền.",
        batch_size=payload.batch_size
    )

@router.get("/auto-tag/status", response_model=AutoTagStatusResponse)
async def get_auto_tagging_status(admin=Depends(require_admin),
                                 source: SourceGateway = Depends(get_source_gateway),
                                 dashboard_db=Depends(get_dashboard_db)):
    """
    Đọc dữ liệu thống kê gắn nhãn thực tế từ cơ sở dữ liệu MySQL,
    trả về tỷ lệ hoàn thành, trạng thái worker và 10 bài vừa được gắn nhãn gần nhất.
    """
    return await auto_tag_service.get_tagging_status(
        source, dashboard_db, actor_profile_id=admin.source_profile_id,
    )

