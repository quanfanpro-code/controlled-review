"""FastAPI 只读本地复核页面。

提供四个只读页面：
- /projects/new：创建项目（表单中 mapping_confirmation 默认为 skip，可跳过对应关系确认）
- /projects/{project_id}/mapping：对应关系查看页
- /projects/{project_id}/progress：进度查看页
- /projects/{project_id}/results：结果浏览页（只浏览和下载，不含整改类操作）

设计要点：
- 所有页面只读，不直接写数据库；写入操作由本地核心 AppService 处理。
- 服务只监听 127.0.0.1（实际运行时由 uvicorn --host 127.0.0.1 控制）。
- 结果页不包含 "认领"、"整改"、"回复"、"关闭"、"误报" 等整改类动作文案。

适配说明：
- 简报原样代码 templates.TemplateResponse("progress.html", {"progress": service.progress(project_id)})
  使用旧版 starlette 签名（name 在前，request 放在 context dict 中）。
- 当前环境 starlette 1.3.1 切换到新签名 TemplateResponse(request, name, context)，
  旧版用法会触发 TypeError。此处适配新版签名，核心逻辑（路由、页面拆分、上下文数据）保持不变。
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# 用 __file__ 计算模板目录，避免硬编码绝对路径
_TEMPLATES_DIR = str(Path(__file__).parent / "templates")

app = FastAPI()
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


@app.get("/projects/new", response_class=HTMLResponse)
def create_project(request: Request):
    """创建项目页面。

    表单中 mapping_confirmation 字段默认值为 "skip"，
    对应关系确认需用户主动选择（默认跳过）。
    """
    return templates.TemplateResponse(request, "create.html")


@app.get("/projects/{project_id}/mapping", response_class=HTMLResponse)
def mapping(project_id: str, request: Request):
    """对应关系查看页（只读）。"""
    return templates.TemplateResponse(
        request,
        "mapping.html",
        {"project_id": project_id},
    )


@app.get("/projects/{project_id}/progress", response_class=HTMLResponse)
def progress(project_id: str, request: Request):
    """进度查看页（只读）。

    简报原样代码：templates.TemplateResponse("progress.html", {"progress": service.progress(project_id)})
    此处适配新版 starlette 签名 TemplateResponse(request, name, context)，
    核心逻辑（返回 progress.html 与 progress 上下文数据）保持不变。
    实际进度数据由本地核心 AppService.project_progress(project_id) 提供，当前用占位值。
    """
    # ponytail: 占位进度数据，实际由 AppService 接入后替换
    progress_data = {"completed": 0, "total": 0}
    return templates.TemplateResponse(
        request,
        "progress.html",
        {"project_id": project_id, "progress": progress_data},
    )


@app.get("/projects/{project_id}/results", response_class=HTMLResponse)
def results(project_id: str, request: Request):
    """结果浏览页（只读，只能浏览和下载）。

    不包含整改类动作按钮（认领、整改、回复、关闭、误报）。
    所有显示数据来自本地核心。
    """
    return templates.TemplateResponse(
        request,
        "results.html",
        {"project_id": project_id},
    )
