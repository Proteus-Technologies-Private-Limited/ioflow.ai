import axios from 'axios';

const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return { Authorization: `Bearer ${token}` };
};

const hitlService = {
  // Roles
  getRoles: () =>
    axios.get('/api/v1/hitl/roles', { headers: getAuthHeaders() }),

  createRole: (data) =>
    axios.post('/api/v1/hitl/roles', data, { headers: getAuthHeaders() }),

  updateRole: (roleId, data) =>
    axios.put(`/api/v1/hitl/roles/${roleId}`, data, { headers: getAuthHeaders() }),

  deleteRole: (roleId) =>
    axios.delete(`/api/v1/hitl/roles/${roleId}`, { headers: getAuthHeaders() }),

  getRoleUsers: (roleId) =>
    axios.get(`/api/v1/hitl/roles/${roleId}/users`, { headers: getAuthHeaders() }),

  assignUsersToRole: (roleId, userIds) =>
    axios.post(`/api/v1/hitl/roles/${roleId}/users`, { user_ids: userIds }, { headers: getAuthHeaders() }),

  removeUserFromRole: (roleId, userId) =>
    axios.delete(`/api/v1/hitl/roles/${roleId}/users/${userId}`, { headers: getAuthHeaders() }),

  // Tasks
  getTasks: (params = {}) =>
    axios.get('/api/v1/hitl/tasks', { params, headers: getAuthHeaders() }),

  getTask: (taskId) =>
    axios.get(`/api/v1/hitl/tasks/${taskId}`, { headers: getAuthHeaders() }),

  completeTask: (taskId, data) =>
    axios.post(`/api/v1/hitl/tasks/${taskId}/complete`, data, { headers: getAuthHeaders() }),

  reassignTask: (taskId, data) =>
    axios.post(`/api/v1/hitl/tasks/${taskId}/reassign`, data, { headers: getAuthHeaders() }),

  cancelTask: (taskId) =>
    axios.post(`/api/v1/hitl/tasks/${taskId}/cancel`, {}, { headers: getAuthHeaders() }),

  getTaskStats: () =>
    axios.get('/api/v1/hitl/tasks/stats', { headers: getAuthHeaders() }),
};

export default hitlService;
