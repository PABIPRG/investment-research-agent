---
name: huohuo-notifications
description: 用户要求查询通知状态、调整提醒开关、静默时段、渠道偏好、清除渠道配置或回访投递记录时使用。聊天只接入受控非密钥操作，凭据在安全表单填写。
---

# 联系偏好与通知回访

先用 read_notification_settings 读取脱敏配置与 revision，list_notification_deliveries 读取真实投递记录。没有记录不表示条件未成立；需要理由用 get_mandate 查看联系决定。accepted 是渠道受理，unknown 是结果未知，应用内 delivered 不代表外部送达或用户已读，不自动重发。

用户明确调整提醒开关、已配置渠道或静默时段时，用当前配置补齐保留项，通过 update_notification_preferences 展示前后值并取得原生确认。明确时区，跨午夜有效；开始结束相同意味着全天静默，不能默认为关闭。用户取消或跳过则不保存；冲突先刷新，提交结果未知先读配置核对，不盲目重试。

全局配置与具体委托允许渠道分别维护。启用渠道不扩大任何委托授权；如需调整某项委托，用 huohuo-mandates 的 manage_mandate 并确认其影响。保存不发送测试消息，不承诺正在后台监控。

用户要填写或更换企业微信/Server 酱密钥、SMTP 密码与收件目标时，用 open_product_view 打开 notifications 安全表单；不要要求用户粘贴密钥到聊天。完成后读取脱敏配置核对“是否配置”，不能声称真实送达。用户明确要删除配置时可用 clear_notification_channel，原生确认会说明不可恢复与剩余渠道。

回访某条记录时读取其真实 mandate_id，可用 open_product_view 定位委托。该工具返回可点击入口链接，用户点击才导航；不要说已打开、已保存或已发送。
