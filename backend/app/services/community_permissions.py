"""What each community role may do — backend_flow.md sections 14 and 15.

Kept deliberately separate from `services/entitlements.py`, because they answer
different questions and section 32 requires both to be asked:

    entitlement  — does this member's *plan* include the capability at all?
    permission   — does this member's *role in this community* allow the action?

A Professional-plan member with no role in a community may not remove its
members; a Member-plan owner of a community may. Neither check substitutes for
the other, and the order is always entitlement first (it is cheaper and it is
what produces the upgrade prompt), then permission.

`LABELS` carries section 15's human wording, so the API can say "Remove Members"
where the code says `MEMBER_REMOVE`.
"""

from __future__ import annotations

from app.core import errors
from app.models import ROLE_RANK, CommunityRole


class Permission:
    VIEW_COMMUNITY = "VIEW_COMMUNITY"
    JOIN_COMMUNITY = "JOIN_COMMUNITY"

    POST_CREATE = "POST_CREATE"
    POST_EDIT = "POST_EDIT"
    POST_DELETE = "POST_DELETE"
    COMMENT_CREATE = "COMMENT_CREATE"
    REACT = "REACT"

    MESSAGE_SEND = "MESSAGE_SEND"
    MESSAGE_DIRECT = "MESSAGE_DIRECT"
    GROUP_CHAT_CREATE = "GROUP_CHAT_CREATE"

    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    FILE_SHARE = "FILE_SHARE"

    MEMBER_INVITE = "MEMBER_INVITE"
    MEMBER_ADD = "MEMBER_ADD"
    MEMBER_REMOVE = "MEMBER_REMOVE"
    MEMBER_BAN = "MEMBER_BAN"
    MEMBER_MUTE = "MEMBER_MUTE"
    MEMBER_MANAGE = "MEMBER_MANAGE"

    CHANNEL_CREATE = "CHANNEL_CREATE"
    CHANNEL_DELETE = "CHANNEL_DELETE"
    CHANNEL_MANAGE = "CHANNEL_MANAGE"

    COMMUNITY_MANAGE = "COMMUNITY_MANAGE"
    COMMUNITY_ARCHIVE = "COMMUNITY_ARCHIVE"
    COMMUNITY_DELETE = "COMMUNITY_DELETE"
    ROLE_MANAGE = "ROLE_MANAGE"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"
    MODERATION_MANAGE = "MODERATION_MANAGE"


#: Section 15's wording, for API responses and the admin UI.
LABELS: dict[str, str] = {
    Permission.VIEW_COMMUNITY: "View Community",
    Permission.JOIN_COMMUNITY: "Join Community",
    Permission.POST_CREATE: "Create Post",
    Permission.POST_EDIT: "Edit Post",
    Permission.POST_DELETE: "Delete Post",
    Permission.COMMENT_CREATE: "Comment on Posts",
    Permission.REACT: "React to Content",
    Permission.MESSAGE_SEND: "Send Messages",
    Permission.MESSAGE_DIRECT: "Send Direct Messages",
    Permission.GROUP_CHAT_CREATE: "Create Group Chat",
    Permission.FILE_UPLOAD: "Upload Files",
    Permission.FILE_DOWNLOAD: "Download Files",
    Permission.FILE_SHARE: "Share Files",
    Permission.MEMBER_INVITE: "Invite Members",
    Permission.MEMBER_ADD: "Add Members",
    Permission.MEMBER_REMOVE: "Remove Members",
    Permission.MEMBER_BAN: "Ban Members",
    Permission.MEMBER_MUTE: "Mute Members",
    Permission.MEMBER_MANAGE: "Manage Members",
    Permission.CHANNEL_CREATE: "Create Channels",
    Permission.CHANNEL_DELETE: "Delete Channels",
    Permission.CHANNEL_MANAGE: "Manage Channels",
    Permission.COMMUNITY_MANAGE: "Manage Community",
    Permission.COMMUNITY_ARCHIVE: "Archive Community",
    Permission.COMMUNITY_DELETE: "Delete Community",
    Permission.ROLE_MANAGE: "Manage Roles",
    Permission.OWNERSHIP_TRANSFER: "Transfer Ownership",
    Permission.MODERATION_MANAGE: "Manage Moderation",
}

# Built cumulatively: each role is the one below it plus what section 14 adds.
#
# VIEWER is the read-only floor. It deliberately carries no verb that produces
# content — no post, comment, reaction, message or upload — so "read-only" is a
# property of this set rather than a flag checked somewhere else. Downloading is
# included because reading a community that has files but withholding the files
# is not read access, it is a different (and unasked-for) restriction.
_VIEWER = frozenset({
    Permission.VIEW_COMMUNITY,
    Permission.JOIN_COMMUNITY,
    Permission.FILE_DOWNLOAD,
})

_MEMBER = _VIEWER | {
    Permission.POST_CREATE,
    Permission.POST_EDIT,
    Permission.COMMENT_CREATE,
    Permission.REACT,
    Permission.MESSAGE_SEND,
    Permission.MESSAGE_DIRECT,
    Permission.FILE_UPLOAD,
}

_MODERATOR = _MEMBER | {
    Permission.POST_DELETE,
    Permission.MEMBER_MUTE,
    Permission.MEMBER_REMOVE,
    Permission.MODERATION_MANAGE,
}

_ADMIN = _MODERATOR | {
    # Section 14 gives an admin "all member management". `outranks` keeps this
    # honest: an admin can appoint a moderator but cannot create another admin,
    # because equal ranks do not outrank each other. Only the owner, sitting a
    # rank higher, can hand out ADMIN.
    Permission.ROLE_MANAGE,
    Permission.MEMBER_INVITE,
    Permission.MEMBER_ADD,
    Permission.MEMBER_BAN,
    Permission.MEMBER_MANAGE,
    Permission.CHANNEL_CREATE,
    Permission.CHANNEL_DELETE,
    Permission.CHANNEL_MANAGE,
    Permission.COMMUNITY_MANAGE,
    Permission.FILE_SHARE,
    Permission.GROUP_CHAT_CREATE,
}

# Archive, delete and ownership transfer are the owner's alone
# (section 14: "Full control including ownership transfer").
_OWNER = _ADMIN | {
    Permission.COMMUNITY_ARCHIVE,
    Permission.COMMUNITY_DELETE,
    Permission.OWNERSHIP_TRANSFER,
}

ROLE_PERMISSIONS: dict[CommunityRole, frozenset[str]] = {
    CommunityRole.viewer: _VIEWER,
    CommunityRole.member: frozenset(_MEMBER),
    CommunityRole.moderator: frozenset(_MODERATOR),
    CommunityRole.admin: frozenset(_ADMIN),
    CommunityRole.owner: frozenset(_OWNER),
}


def permissions_for(role: CommunityRole) -> frozenset[str]:
    return ROLE_PERMISSIONS[role]


def role_allows(role: CommunityRole, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def meets_rank(role: CommunityRole, required: CommunityRole) -> bool:
    """At least `required`. Unlike `outranks`, holding the rank itself is enough.

    This is the question a *gate* asks ("may you post here?"), where `outranks`
    answers the question an *action on someone else* asks ("may you demote
    them?"). Keeping them apart is what stops an admin being locked out of a
    community set to admin-only posting.
    """
    return ROLE_RANK[role] >= ROLE_RANK[required]


#: How to say "you are not senior enough to post here" for each setting.
#: `viewer` is absent because it gates nothing — everyone meets it. `member` is
#: present now that `viewer` sits below it, though a viewer is normally refused
#: earlier, by POST_CREATE simply not being in their permission set.
POST_REFUSAL: dict[CommunityRole, str] = {
    CommunityRole.member: "Viewers cannot post in this community.",
    CommunityRole.admin: "Only admins can post in this community.",
    CommunityRole.moderator:
        "Only moderators and admins can post in this community.",
    CommunityRole.owner: "Only the owner can post in this community.",
}


#: Roles that carry no authority over anyone else — no member management, no
#: role management, no moderation. Offering one of these cannot escalate
#: anything, which is why inviting is allowed to hand them out sideways: a
#: member inviting another member is the point of an open invite policy, while
#: an admin minting a peer admin is still privilege escalation.
UNPRIVILEGED_ROLES = frozenset({CommunityRole.viewer, CommunityRole.member})


def may_grant(actor: CommunityRole, role: CommunityRole) -> bool:
    """Whether `actor` may hand out `role`.

    Two ways to qualify, and the second is what makes member-to-member invites
    work without opening a hole:

      * you outrank the role — an owner granting admin, an admin granting
        moderator; strictly above, so peers cannot mint peers;
      * or the role carries no authority at all, in which case granting it to
        someone changes nothing about who can act on whom.
    """
    return role in UNPRIVILEGED_ROLES or outranks(actor, role)


def outranks(actor: CommunityRole, target: CommunityRole) -> bool:
    """Strictly above. Equal ranks do not outrank each other.

    This is what stops an admin removing, banning or demoting another admin —
    and what stops anyone at all acting on the owner.
    """
    return ROLE_RANK[actor] > ROLE_RANK[target]


def require(role: CommunityRole, permission: str) -> None:
    if role_allows(role, permission):
        return
    raise errors.forbidden(
        errors.Code.PERMISSION_DENIED,
        f"Your role in this community does not allow: {LABELS.get(permission, permission)}.",
        permission=permission,
        role=role.value,
    )


def require_outranks(actor: CommunityRole, target: CommunityRole, *, action: str) -> None:
    if outranks(actor, target):
        return
    if target is CommunityRole.owner:
        message = "The community owner cannot be the target of that action."
    else:
        message = f"You cannot {action} someone at your own level or above."
    raise errors.forbidden(
        errors.Code.PERMISSION_DENIED, message,
        actor_role=actor.value, target_role=target.value,
    )
