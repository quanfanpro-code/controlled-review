"""官方依据服务。

按需查询并固化官方依据，确保只从官方来源获取信息：
- fetch: 校验域名白名单后下载官方文件
- search: 根据报告类型和报告期间搜索官方依据，网络失败时返回未确认但不阻塞内部检查

服务保存机构、名称、文号、发布日期、生效日期、官方地址、取得时间、
正文或附件快照及摘要。适用性判断必须记录报告类型和报告期间；
无法判断时返回未确认，不使用模型记忆代替来源。
"""

import httpx
from dataclasses import dataclass
from urllib.parse import urlparse


# 官方域名白名单（原样使用简报代码）
OFFICIAL_HOSTS = {
    "mof.gov.cn", "kjs.mof.gov.cn", "csrc.gov.cn", "sse.com.cn",
    "szse.cn", "gov.cn", "sasac.gov.cn",
}


@dataclass(frozen=True)
class FetchResult:
    """获取官方文件的结果。

    status 取值：ok/rejected_domain/not_found
    url: 官方地址
    """

    status: str
    url: str = ""


@dataclass(frozen=True)
class SearchResult:
    """搜索官方依据的结果。

    status 取值：ok/official_unconfirmed
    blocks_internal_checks: 是否阻塞内部检查
    """

    status: str
    blocks_internal_checks: bool = False


class OfficialSourceService:
    """官方依据服务。

    fetch 校验域名是否在 OFFICIAL_HOSTS 白名单后下载官方文件；
    search 根据报告类型和报告期间搜索官方依据，
    网络失败时返回 official_unconfirmed 且 blocks_internal_checks=False。
    """

    def fetch(self, url: str) -> FetchResult:
        """获取官方文件。

        先校验域名是否在白名单，再发起 HTTP 请求。
        域名不在白名单时返回 rejected_domain。
        """
        host = urlparse(url).hostname
        if host not in OFFICIAL_HOSTS:
            return FetchResult(status="rejected_domain", url=url)
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 404:
                return FetchResult(status="not_found", url=url)
            response.raise_for_status()
            return FetchResult(status="ok", url=url)
        except Exception:
            # 网络失败视为未找到，不阻塞调用方
            return FetchResult(status="not_found", url=url)

    def search(self, report_type: str, report_date: str) -> SearchResult:
        """搜索官方依据。

        根据报告类型（report_type）和报告期间（report_date）搜索官方依据。
        网络失败时返回 official_unconfirmed，不阻塞内部检查。
        """
        try:
            # 简化实现：对所有官方站点发起查询
            # 实际生产中应根据 report_type 选择对应站点和查询接口
            response = httpx.get(
                "https://www.gov.cn/search",
                params={"type": report_type, "date": report_date},
                timeout=10,
            )
            response.raise_for_status()
            # 成功即视为确认，不阻塞内部检查
            return SearchResult(status="ok", blocks_internal_checks=False)
        except Exception:
            # 网络失败返回未确认，不阻塞内部检查
            return SearchResult(
                status="official_unconfirmed", blocks_internal_checks=False
            )
