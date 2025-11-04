import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 默认配置路径优先级：
# 1) 环境变量 A_SHARE_AGENT_CONFIG 指定路径
# 2) 项目根目录 config.json
# 3) 用户目录 ~/.a_share_agent/config.json

_CONFIG: Dict[str, Any] = {}


def _default_paths() -> list:
	root = Path(__file__).resolve().parents[1]  # 项目根目录
	paths = []
	if os.getenv('A_SHARE_AGENT_CONFIG'):
		paths.append(Path(os.getenv('A_SHARE_AGENT_CONFIG')).expanduser())
	paths.append(root / 'config.json')
	paths.append(Path.home() / '.a_share_agent' / 'config.json')
	return paths


def _load_first_existing(paths: list) -> Optional[Dict[str, Any]]:
	for p in paths:
		try:
			if p.exists():
				with p.open('r', encoding='utf-8') as f:
					return json.load(f)
		except Exception:
			continue
	return None


def load_config(refresh: bool = False) -> Dict[str, Any]:
	global _CONFIG
	if _CONFIG and not refresh:
		return _CONFIG
	cfg = _load_first_existing(_default_paths()) or {}
	_CONFIG = cfg
	return _CONFIG


def _get_by_path(d: Dict[str, Any], path: str) -> Any:
	cur: Any = d
	for key in path.split('.'):
		if not isinstance(cur, dict):
			return None
		if key not in cur:
			return None
		cur = cur[key]
	return cur


def get_config_value(path: str, default: Any = None) -> Any:
	"""从 JSON 配置读取指定 path（点号分隔），不存在则返回 default。"""
	cfg = load_config()
	val = _get_by_path(cfg, path)
	return default if val is None else val


def get_with_env(path: str, env_var: str, default: Any = None) -> Any:
	"""优先从 JSON path 读取，其次读环境变量 env_var，最后 default。"""
	val = get_config_value(path, None)
	if val is not None and val != "":
		return val
	envv = os.getenv(env_var)
	if envv is not None and envv != "":
		return envv
	return default


def ensure_example(path: Optional[str] = None) -> Path:
	"""在项目根目录生成示例 config.example.json（若不存在）。"""
	root = Path(__file__).resolve().parents[1]
	example = root / 'config.example.json'
	if example.exists():
		return example
	data = {
		"model": {"name": "deepseek"},
		"deepseek": {"api_key": "sk-xxxx", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
		"openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
		"tushare": {"token": "your_tushare_token"}
	}
	example.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
	return example
