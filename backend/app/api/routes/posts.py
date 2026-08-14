"""The feed: posts, likes and comments."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession
from app.models import (
    Community, CommunityMember, MediaAsset, MembershipStatus, Post, PostAttachment,
    PostComment, PostLike, VisibilityLevel,
)
from app.schemas.common import Message, Page
from app.schemas.media import MediaRef
from app.schemas.post import (
    CommentCreate, CommentOut, LikeState, PostCommunity, PostCreate, PostOut,
)
from app.schemas.user import UserSummary

router = APIRouter(prefix="/posts", tags=["feed"])


async def _joined_community_ids(db: DbSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await db.scalars(
                select(CommunityMember.community_id).where(
                    CommunityMember.user_id == user_id,
                    CommunityMember.status == MembershipStatus.joined,
                )
            )
        ).all()
    )


async def _require_membership(db: DbSession, community_id: uuid.UUID, user_id: uuid.UUID) -> None:
    membership = await db.scalar(
        select(CommunityMember.id).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user_id,
            CommunityMember.status == MembershipStatus.joined,
        )
    )
    if membership is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Join the community to see its discussion"
        )


async def _require_can_read(db: DbSession, post: Post, user_id: uuid.UUID) -> None:
    """A post inside a community is only readable by that community's members,
    and a Private post is only readable by its author."""
    if post.visibility is VisibilityLevel.private and post.author_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This post is private")
    if post.community_id is not None:
        await _require_membership(db, post.community_id, user_id)


def _to_out(post: Post, liked_by_me: bool) -> PostOut:
    """Build the response explicitly.

    `PostOut.model_validate(post)` cannot be used here: it would try to coerce the
    PostAttachment join rows into MediaRef and fail. The media has to be unwrapped
    from the join row first.
    """
    return PostOut(
        id=post.id,
        body=post.body,
        embed_title=post.embed_title,
        embed_detail=post.embed_detail,
        visibility=post.visibility,
        created_at=post.created_at,
        author=UserSummary.model_validate(post.author),
        community=(
            PostCommunity.model_validate(post.community) if post.community else None
        ),
        like_count=len(post.likes),
        comment_count=len(post.comments),
        liked_by_me=liked_by_me,
        attachments=[
            MediaRef(
                id=a.media.id,
                kind=a.media.kind,
                url=f"/media/{a.media.stored_name}",
                original_name=a.media.original_name,
                content_type=a.media.content_type,
                size_bytes=a.media.size_bytes,
            )
            for a in post.attachments
            if a.media is not None
        ],
    )


@router.get("", response_model=Page[PostOut])
async def list_feed(
    db: DbSession,
    current_user: CurrentUser,
    community_id: uuid.UUID | None = Query(default=None),
    author_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> Page[PostOut]:
    filters = []

    if community_id is not None:
        # Asking for one community's feed requires membership of it.
        await _require_membership(db, community_id, current_user.id)
        filters.append(Post.community_id == community_id)
    else:
        # The global feed shows unattached posts plus those from communities the
        # caller has actually joined — never another community's discussion.
        visible = await _joined_community_ids(db, current_user.id)
        filters.append(
            or_(Post.community_id.is_(None), Post.community_id.in_(visible))
            if visible
            else Post.community_id.is_(None)
        )

    if author_id is not None:
        filters.append(Post.author_id == author_id)

    # `Private` means the author only. Without this the field was decoration.
    filters.append(
        or_(Post.visibility != VisibilityLevel.private, Post.author_id == current_user.id)
    )

    count_statement = select(func.count(Post.id)).where(*filters)
    statement = select(Post).where(*filters)

    total = await db.scalar(count_statement) or 0
    posts = (
        await db.scalars(
            statement.order_by(Post.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    liked = set(
        (
            await db.scalars(
                select(PostLike.post_id).where(
                    PostLike.user_id == current_user.id,
                    PostLike.post_id.in_([p.id for p in posts] or [uuid.uuid4()]),
                )
            )
        ).all()
    )

    return Page(
        items=[_to_out(p, p.id in liked) for p in posts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate, current_user: CurrentUser, db: DbSession
) -> PostOut:
    if payload.community_id is not None:
        community = await db.get(Community, payload.community_id)
        if community is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Community not found")

        membership = await db.scalar(
            select(CommunityMember).where(
                CommunityMember.community_id == community.id,
                CommunityMember.user_id == current_user.id,
                CommunityMember.status == MembershipStatus.joined,
            )
        )
        if membership is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Join the community before posting in it"
            )

    data = payload.model_dump()
    # dict.fromkeys de-duplicates while keeping the order the client sent.
    attachment_ids = list(dict.fromkeys(data.pop("attachment_ids", [])))

    post = Post(author_id=current_user.id, **data)
    db.add(post)
    await db.flush()

    # Only the uploader may attach a file, so one member cannot staple another
    # member's private document onto their own post.
    if attachment_ids:
        owned = {
            m.id: m
            for m in (
                await db.scalars(
                    select(MediaAsset).where(
                        MediaAsset.id.in_(attachment_ids),
                        MediaAsset.owner_id == current_user.id,
                    )
                )
            ).all()
        }
        missing = [str(i) for i in attachment_ids if i not in owned]
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Upload not found or not yours: {', '.join(missing)}",
            )
        for position, media_id in enumerate(attachment_ids):
            db.add(PostAttachment(post_id=post.id, media_id=media_id, position=position))

    await db.commit()
    await db.refresh(post)
    return _to_out(post, liked_by_me=False)


@router.get("/{post_id}", response_model=PostOut)
async def read_post(post_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> PostOut:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await _require_can_read(db, post, current_user.id)

    liked = await db.scalar(
        select(PostLike.id).where(
            PostLike.post_id == post.id, PostLike.user_id == current_user.id
        )
    )
    return _to_out(post, liked is not None)


@router.delete("/{post_id}", response_model=Message)
async def delete_post(post_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Message:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts")

    await db.delete(post)
    await db.commit()
    return Message(detail="Post deleted")


@router.post("/{post_id}/like", response_model=LikeState)
async def toggle_like(
    post_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> LikeState:
    """Idempotent toggle — calling it again removes the like."""
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await _require_can_read(db, post, current_user.id)

    existing = await db.scalar(
        select(PostLike).where(
            PostLike.post_id == post.id, PostLike.user_id == current_user.id
        )
    )
    if existing is None:
        db.add(PostLike(post_id=post.id, user_id=current_user.id))
        liked = True
    else:
        await db.delete(existing)
        liked = False

    await db.commit()
    count = await db.scalar(select(func.count(PostLike.id)).where(PostLike.post_id == post.id))
    return LikeState(liked=liked, like_count=count or 0)


@router.get("/{post_id}/comments", response_model=list[CommentOut])
async def list_comments(post_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await _require_can_read(db, post, current_user.id)

    rows = (
        await db.scalars(
            select(PostComment)
            .where(PostComment.post_id == post.id)
            .order_by(PostComment.created_at)
        )
    ).all()
    return rows


@router.post(
    "/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def add_comment(
    post_id: uuid.UUID, payload: CommentCreate, current_user: CurrentUser, db: DbSession
) -> PostComment:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await _require_can_read(db, post, current_user.id)

    comment = PostComment(post_id=post.id, author_id=current_user.id, body=payload.body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment
