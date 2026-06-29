"""Per-user persistent-workspace repository — Stream J.15.

Registers the docker named volume backing each ``(tenant_id, user_id)``
pair's ``/workspace``. The volume outlives the ephemeral sandbox
containers that mount it. See ``docs/streams/STREAM-J-DESIGN.md`` § 9.
"""

from helix_agent.persistence.workspace.base import (
    UserWorkspaceStore as UserWorkspaceStore,
)
from helix_agent.persistence.workspace.base import (
    WorkspaceNotFoundError as WorkspaceNotFoundError,
)
from helix_agent.persistence.workspace.base import (
    workspace_volume_name as workspace_volume_name,
)
from helix_agent.persistence.workspace.dlq import (
    InMemoryVolumeBackupDLQ as InMemoryVolumeBackupDLQ,
)
from helix_agent.persistence.workspace.dlq import (
    SqlVolumeBackupDLQ as SqlVolumeBackupDLQ,
)
from helix_agent.persistence.workspace.dlq import (
    VolumeBackupDLQ as VolumeBackupDLQ,
)
from helix_agent.persistence.workspace.dlq import (
    VolumeDLQRow as VolumeDLQRow,
)
from helix_agent.persistence.workspace.dlq import (
    VolumeOpKind as VolumeOpKind,
)
from helix_agent.persistence.workspace.layout import (
    WORKSPACE_RESERVED_PREFIXES as WORKSPACE_RESERVED_PREFIXES,
)
from helix_agent.persistence.workspace.layout import (
    WORKSPACE_SKILLS_DIR as WORKSPACE_SKILLS_DIR,
)
from helix_agent.persistence.workspace.layout import (
    WORKSPACE_UPLOADS_DIR as WORKSPACE_UPLOADS_DIR,
)
from helix_agent.persistence.workspace.layout import (
    is_reserved_workspace_path as is_reserved_workspace_path,
)
from helix_agent.persistence.workspace.memory import (
    InMemoryUserWorkspaceStore as InMemoryUserWorkspaceStore,
)
from helix_agent.persistence.workspace.sql import (
    SqlUserWorkspaceStore as SqlUserWorkspaceStore,
)

__all__ = [
    "WORKSPACE_RESERVED_PREFIXES",
    "WORKSPACE_SKILLS_DIR",
    "WORKSPACE_UPLOADS_DIR",
    "InMemoryUserWorkspaceStore",
    "InMemoryVolumeBackupDLQ",
    "SqlUserWorkspaceStore",
    "SqlVolumeBackupDLQ",
    "UserWorkspaceStore",
    "VolumeBackupDLQ",
    "VolumeDLQRow",
    "VolumeOpKind",
    "WorkspaceNotFoundError",
    "is_reserved_workspace_path",
    "workspace_volume_name",
]
