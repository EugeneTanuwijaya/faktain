"""Bounded public HTTP fetches. Pin DNS results, and revalidate every redirect."""
import asyncio
import ipaddress
import socket
import zlib
from urllib.parse import urljoin, urlsplit

import httpx


async def public_target(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL harus menggunakan http atau https")
        if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            raise ValueError("URL dengan kredensial atau port khusus tidak didukung")
        host = parsed.hostname.encode("idna").decode("ascii")
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            resolved = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                               type=socket.SOCK_STREAM)
            addresses = [item[4][0] for item in resolved]
        if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
            raise ValueError("URL harus mengarah ke alamat internet publik")
        ip = addresses[0]
        authority = f"[{ip}]" if ":" in ip else ip
        if parsed.port:
            authority += f":{parsed.port}"
        pinned = parsed._replace(netloc=authority, fragment="").geturl()
        return pinned, host
    except (OSError, UnicodeError) as exc:
        raise ValueError("Alamat URL tidak dapat diresolusi") from exc


async def safe_fetch(url: str, *, max_bytes: int = 2_000_000,
                     accepted_types: tuple[str, ...] = ("text/html", "application/xhtml+xml")) -> tuple[bytes, str, str]:
    current = url
    async with httpx.AsyncClient(timeout=12.0, trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        for _ in range(5):
            pinned, host = await public_target(current)
            parsed = urlsplit(current)
            host_header = host + (f":{parsed.port}" if parsed.port else "")
            async with client.stream("GET", pinned, headers={"Host": host_header, "User-Agent": "AntiHoax-MVP/2.0", "Accept-Encoding": "identity"},
                                     extensions={"sni_hostname": host}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect URL tidak valid")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if mime not in accepted_types:
                    raise ValueError("Jenis konten URL tidak didukung")
                encoding = response.headers.get("content-encoding", "identity").strip().lower()
                if encoding not in {"identity", "gzip", "deflate"}:
                    raise ValueError("Jenis kompresi URL tidak didukung")
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS) if encoding != "identity" else None
                size = 0
                wire_size = 0
                parts = []
                # httpx aiter_bytes decodes without an output limit. Decode raw
                # chunks ourselves so a small compressed bomb cannot allocate
                # its entire expanded payload before our size check.
                async for raw_part in response.aiter_raw():
                    wire_size += len(raw_part)
                    if wire_size > max_bytes:
                        raise ValueError("Konten URL terlalu besar")
                    if decoder and decoder.eof and raw_part:
                        raise ValueError("Konten kompresi memiliki data tambahan setelah selesai")
                    try:
                        part = decoder.decompress(raw_part, max_bytes - size + 1) if decoder else raw_part
                    except zlib.error as exc:
                        raise ValueError("Konten kompresi URL tidak valid") from exc
                    if decoder and decoder.unused_data:
                        raise ValueError("Konten kompresi memiliki data tambahan setelah selesai")
                    size += len(part)
                    if size > max_bytes:
                        raise ValueError("Konten URL terlalu besar")
                    parts.append(part)
                if decoder and not decoder.eof:
                    raise ValueError("Konten kompresi URL tidak lengkap")
                return b"".join(parts), mime, current
    raise ValueError("Terlalu banyak redirect URL")
