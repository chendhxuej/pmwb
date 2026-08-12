/**
 * 督办 API —— 统一走 /api/v1/supervise/*，不直连邮件中心
 * 由后端 supervise 服务代理模板渲染与发送（sup-2 已实现）
 */
import request from './request'

/**
 * 工单督办（运营问题 / 开发工单 / 需求）
 * @param {Object} data
 * @param {'sync'|'urge'} data.scene 场景：sync=信息同步 / urge=催办
 * @param {'work_order'|'operation'|'dev_ticket'|'requirement'} data.ticket_type 工单类型
 * @param {number|string} data.ticket_id 工单 id
 * @param {string[]} data.recipients 收件人（姓名/邮箱，后端按联系人解析）
 * @param {string} [data.extra_msg] 留言
 */
export function superviseTicket(data) {
  return request.post('/supervise/ticket', data)
}

/**
 * 行动项督办（会议行动项）
 * @param {Object} data
 * @param {'sync'|'urge'} data.scene
 * @param {number} data.meeting_id
 * @param {number} data.action_id
 * @param {string[]} data.recipients
 * @param {string} [data.extra_msg]
 */
export function superviseAction(data) {
  return request.post('/supervise/action', data)
}

export default {
  superviseTicket,
  superviseAction,
}
