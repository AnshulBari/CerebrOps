"""
CerebrOps Model Repository

Persists trained anomaly detection models (joblib) alongside versioned,
human-readable "model cards" (JSON). A `current_version` file points at the
active model so the monitor can reload it across restarts instead of
retraining from scratch every boot.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger('cerebrops.model_repository')

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')


class ModelRepository:
    """Filesystem-backed, versioned model store."""

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or os.getenv('CEREBROPS_MODEL_DIR') or DEFAULT_MODEL_DIR
        os.makedirs(self.model_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _model_path(self, version: int) -> str:
        return os.path.join(self.model_dir, f'cerebrops_v{version}.joblib')

    def _card_path(self, version: int) -> str:
        return os.path.join(self.model_dir, f'cerebrops_v{version}_card.json')

    def _current_file(self) -> str:
        return os.path.join(self.model_dir, 'current_version')

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def list_versions(self) -> List[int]:
        versions = []
        if os.path.isdir(self.model_dir):
            for name in os.listdir(self.model_dir):
                if name.startswith('cerebrops_v') and name.endswith('.joblib'):
                    try:
                        versions.append(int(name[len('cerebrops_v'):-len('.joblib')]))
                    except ValueError:
                        continue
        return sorted(versions)

    def next_version(self) -> int:
        versions = self.list_versions()
        return (max(versions) + 1) if versions else 1

    def current_version(self) -> Optional[int]:
        try:
            with open(self._current_file(), 'r', encoding='utf-8') as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def set_current(self, version: int) -> None:
        with open(self._current_file(), 'w', encoding='utf-8') as f:
            f.write(str(version))
        logger.info("Current model version set to %s", version)

    # ------------------------------------------------------------------
    # Save / load
    # ------------------------------------------------------------------

    def save(self, version: int, model: Any, scaler: Any, card: Dict[str, Any]) -> None:
        """Persist model + scaler (joblib) and the model card (JSON)."""
        import joblib
        joblib.dump({'model': model, 'scaler': scaler}, self._model_path(version))
        with open(self._card_path(version), 'w', encoding='utf-8') as f:
            json.dump(card, f, indent=2, default=str)
        logger.info("Persisted model v%s to %s", version, self.model_dir)

    def load(self, version: int) -> Optional[Dict[str, Any]]:
        """Load model + scaler + card for a version; None if missing."""
        import joblib
        model_path = self._model_path(version)
        card_path = self._card_path(version)
        if not os.path.exists(model_path) or not os.path.exists(card_path):
            return None
        payload = joblib.load(model_path)
        with open(card_path, 'r', encoding='utf-8') as f:
            card = json.load(f)
        return {'model': payload['model'], 'scaler': payload['scaler'], 'card': card}
