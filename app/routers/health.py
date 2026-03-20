from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="健康检查")
async def health_check():
    """返回服务存活状态，供 K8s / 负载均衡探针使用。"""
    return {"status": "ok"}
