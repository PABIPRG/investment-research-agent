"""按已解析的标准实体身份归并讨论对象；保留原文提及，不合并实体主数据。"""
import re
from .models import DiscussionSubject, EntityMention


def discussion_subjects(mentions: list[EntityMention], raw_query: str = "") -> list[DiscussionSubject]:
    groups: dict[str, list[EntityMention]] = {}
    for mention in mentions:
        if mention.dynamic_collection_types:
            continue
        # 候选重叠、相同六位代码或相同名称都不是等价证据。
        key = ("entity:" + mention.resolved_entity_id
               if mention.resolution_status == "resolved" and mention.resolved_entity_id
               else "mention:" + mention.mention_id)
        groups.setdefault(key, []).append(mention)
    result = []
    for members in groups.values():
        first = members[0]
        primary = first.resolved_entity_id if first.resolution_status == "resolved" else None
        candidates = list(first.candidates)
        if primary:
            # 消歧已确定任务身份：只确认该身份，关联公司/证券不作为等价选项。
            candidates = [c for c in candidates if c.entity_id == primary]
        result.append(DiscussionSubject(
            subject_id="SUBJECT_" + first.mention_id,
            mention_ids=[m.mention_id for m in members],
            raw_text=" / ".join(dict.fromkeys(m.raw_text for m in members)),
            primary_entity_id=primary,
            resolution_status=first.resolution_status,
            candidates=candidates,
            related_entity_ids=list(dict.fromkeys(c.entity_id for m in members for c in m.candidates
                if primary and c.entity_id != primary
                and c.entity_id in {primary.replace('SEC:CN:A:', 'CO:CN:A:'), primary.replace('CO:CN:A:', 'SEC:CN:A:')}
                and (m.resolution_reason or "").startswith("company_security_pair:"))),
            merge_reason="same_resolved_entity_id" if len(members) > 1 else "single_mention",
        ))
    # 紧邻的名称和代码互相矛盾时，提出一次冲突澄清，不能当成两个授权对象。
    if raw_query and not any(word in raw_query for word in ("比较", "对比", "区别", "vs")):
        by_id = {m.mention_id: m for m in mentions}
        index = 0
        while index + 1 < len(result):
            left, right = result[index:index + 2]
            if len(left.mention_ids) == len(right.mention_ids) == 1:
                a, b = by_id[left.mention_ids[0]], by_id[right.mention_ids[0]]
                adjacent = re.fullmatch(r"[\s（(]*", raw_query[a.end_offset:b.start_offset]) is not None
                name_code = bool(re.fullmatch(r"\d{6}(?:\.(?:SH|SZ|BJ))?", a.raw_text, re.I)) != bool(re.fullmatch(r"\d{6}(?:\.(?:SH|SZ|BJ))?", b.raw_text, re.I))
                if adjacent and name_code and left.primary_entity_id and right.primary_entity_id and left.primary_entity_id != right.primary_entity_id:
                    result[index:index + 2] = [DiscussionSubject(
                        subject_id=left.subject_id, mention_ids=left.mention_ids + right.mention_ids,
                        raw_text=left.raw_text + " / " + right.raw_text,
                        resolution_status="ambiguous", candidates=left.candidates + right.candidates,
                        merge_reason="name_code_conflict",
                    )]
                    continue
            index += 1
    return result
