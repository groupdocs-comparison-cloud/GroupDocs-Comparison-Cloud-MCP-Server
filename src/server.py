import base64
import os
import shutil
import tempfile

import groupdocs_comparison_cloud as sdk
from mcp.server.fastmcp import FastMCP

from server_helpers import decode_base64_bytes, json_safe_metadata, obj_to_model_kwargs
from server_models import DownloadedFile, StorageFile, SupportedFileFormat


_mcp_port_raw = os.environ.get("MCP_PORT", "8000")
try:
    _mcp_port = int(_mcp_port_raw)
except ValueError:
    _mcp_port = 8000
_mcp_host = os.environ.get("MCP_HOST", "127.0.0.1")
mcp = FastMCP("mcp-groupdocs-comparison-cloud", host=_mcp_host, port=_mcp_port)

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
if not client_id or not client_secret:
    raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in environment variables")

configuration = sdk.Configuration(client_id, client_secret)
if hasattr(configuration, "api_base_url"):
    configuration.api_base_url = "https://api.groupdocs.cloud"
if hasattr(configuration, "timeout"):
    configuration.timeout = 180


def _to_dict(value):
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        return json_safe_metadata(value.to_dict())
    if isinstance(value, dict):
        return json_safe_metadata(value)
    return json_safe_metadata(getattr(value, "__dict__", {}))


def _new(name: str, *args, **kwargs):
    cls = getattr(sdk, name)
    if kwargs:
        try:
            return cls(**kwargs)
        except Exception:
            pass
    if args:
        try:
            return cls(*args)
        except Exception:
            pass
    return cls()


def _call_any(obj, names: list[str], *args):
    last_err = None
    for name in names:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        try:
            return fn(*args)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise AttributeError(f"No callable method from candidates: {names}")


def _get_api(name: str):
    cls = getattr(sdk, name)
    if hasattr(cls, "from_config"):
        return cls.from_config(configuration)
    if hasattr(cls, "from_keys"):
        return cls.from_keys(client_id, client_secret)
    return cls(configuration)


def _req_with_file_info(file_info, request_names: list[str]):
    for req_name in request_names:
        req_cls = getattr(sdk, req_name, None)
        if req_cls is None:
            continue
        for payload in ({"file_info": file_info}, {"fileInfo": file_info}):
            try:
                return req_cls(**payload)
            except Exception:
                pass
        try:
            return req_cls(file_info)
        except Exception:
            pass
    raise AttributeError("No supported request class found")


def _req_with_options(options, request_names: list[str]):
    for req_name in request_names:
        req_cls = getattr(sdk, req_name, None)
        if req_cls is None:
            continue
        for payload in ({"options": options}, {"extract_options": options}, {"annotate_options": options}):
            try:
                return req_cls(**payload)
            except Exception:
                pass
        try:
            return req_cls(options)
        except Exception:
            pass
    raise AttributeError("No supported options request class found")


def _formats_from_result(result) -> list[SupportedFileFormat]:
    raw = getattr(result, "formats", None)
    if raw is None and isinstance(result, list):
        raw = result
    raw = raw or []
    out = []
    for item in raw:
        out.append(SupportedFileFormat(file_format=getattr(item, "file_format", None) or getattr(item, "format", None), extension=getattr(item, "extension", None)))
    return out


# =====================================================================
# Comparison-scoped tools
# =====================================================================

@mcp.tool()
def comparison_supported_formats() -> list[SupportedFileFormat]:
    info_api = _get_api("InfoApi")
    result = _call_any(info_api, ["get_supported_file_formats"])
    return _formats_from_result(result)


@mcp.tool()
def comparison_compare(source_file_path: str, target_file_path: str, output_path: str, storage_name: str | None = None) -> dict:
    compare_api = _get_api("CompareApi")
    source = _new("FileInfo", file_path=source_file_path, storage_name=storage_name)
    target = _new("FileInfo", file_path=target_file_path, storage_name=storage_name)
    options = _new("ComparisonOptions", source_file=source, target_files=[target], output_path=output_path)
    req = _new("ComparisonsRequest", options)
    result = _call_any(compare_api, ["comparisons", "compare"], req)
    return _to_dict(result)


# =====================================================================
# Shared storage/file methods
# =====================================================================


@mcp.tool()
def file_upload(file_stream: bytes, cloud_path: str) -> str:
    if isinstance(file_stream, str):
        file_stream = base64.b64decode(file_stream, validate=True)
    elif isinstance(file_stream, (bytearray, memoryview)):
        file_stream = bytes(file_stream)
    elif not isinstance(file_stream, bytes):
        raise TypeError(f"Unsupported type for file_stream: {type(file_stream)}")

    file_stream = decode_base64_bytes(file_stream)

    _, ext = os.path.splitext(cloud_path)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(file_stream)
            tmp_file.flush()

        request = sdk.UploadFileRequest(cloud_path, tmp_path)
        file_api = sdk.FileApi.from_config(configuration)
        file_api.upload_file(request)
        return f"File uploaded successfully to: {cloud_path}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@mcp.tool()
def file_upload_local(local_path: str, cloud_path: str) -> str:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")
    if not os.path.isfile(local_path):
        raise IsADirectoryError(f"Expected a file but got directory: {local_path}")

    file_api = sdk.FileApi.from_config(configuration)
    request = sdk.UploadFileRequest(cloud_path, local_path)
    file_api.upload_file(request)
    return f"File uploaded successfully to: {cloud_path}"


@mcp.tool()
def file_download(path: str) -> DownloadedFile:
    file_api = sdk.FileApi.from_config(configuration)
    request = sdk.DownloadFileRequest(path)
    local_path = file_api.download_file(request)

    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Downloaded file not found at: {local_path}")

    try:
        with open(local_path, "rb") as f:
            data = f.read()

        return DownloadedFile(
            path=path,
            name=os.path.basename(path),
            base64_data=base64.b64encode(data).decode("ascii"),
            size=len(data),
        )
    finally:
        try:
            os.remove(local_path)
        except Exception:
            pass


@mcp.tool()
def file_download_local(path: str, local_path: str) -> str:
    file_api = sdk.FileApi.from_config(configuration)
    request = sdk.DownloadFileRequest(path)
    tmp_path = file_api.download_file(request)

    if not os.path.exists(tmp_path):
        raise FileNotFoundError(f"Downloaded file not found at: {tmp_path}")

    target_dir = os.path.dirname(local_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    if os.path.isfile(local_path):
        os.remove(local_path)

    shutil.move(tmp_path, local_path)
    return f"File downloaded successfully to local path: {local_path}"


@mcp.tool()
def folder_list(path: str = "/") -> list[StorageFile]:
    folder_api = sdk.FolderApi.from_config(configuration)
    result = folder_api.get_files_list(sdk.GetFilesListRequest(path))
    items = getattr(result, "value", []) or []
    return [StorageFile(**obj_to_model_kwargs(it, StorageFile)) for it in items]


@mcp.tool()
def file_exists(path: str) -> bool:
    storage_api = sdk.StorageApi.from_config(configuration)
    response = storage_api.object_exists(sdk.ObjectExistsRequest(path))
    return bool(response.exists and not getattr(response, "is_folder", False))


@mcp.tool()
def folder_exists(path: str) -> bool:
    storage_api = sdk.StorageApi.from_config(configuration)
    response = storage_api.object_exists(sdk.ObjectExistsRequest(path))
    return bool(response.exists and getattr(response, "is_folder", False))


@mcp.tool()
def file_delete(path: str) -> bool:
    file_api = sdk.FileApi.from_config(configuration)
    file_api.delete_file(sdk.DeleteFileRequest(path))
    return True


@mcp.tool()
def folder_delete(path: str, recursive: bool = True) -> bool:
    folder_api = sdk.FolderApi.from_config(configuration)
    folder_api.delete_folder(sdk.DeleteFolderRequest(path, recursive=recursive))
    return True


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
