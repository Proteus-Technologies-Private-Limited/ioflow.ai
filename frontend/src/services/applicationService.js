class ApplicationService {
  constructor() {
    this.baseUrl = '/api/v1';
  }

  async getHeaders() {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
  }

  async getApplications() {
    try {
      const response = await fetch(`${this.baseUrl}/applications`, {
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching applications:', error);
      throw error;
    }
  }

  async getApplication(appId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}`, {
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching application:', error);
      throw error;
    }
  }

  async getServices(appId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/services`, {
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching services:', error);
      throw error;
    }
  }

  async getService(appId, serviceId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/services/${serviceId}`, {
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching service:', error);
      throw error;
    }
  }

  async updateService(appId, serviceId, updateData) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/services/${serviceId}`, {
        method: 'PUT',
        headers: await this.getHeaders(),
        body: JSON.stringify(updateData)
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error updating service:', error);
      throw error;
    }
  }

  async createService(appId, serviceData) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/services`, {
        method: 'POST',
        headers: await this.getHeaders(),
        body: JSON.stringify(serviceData)
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error creating service:', error);
      throw error;
    }
  }

  async deleteService(appId, serviceId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/services/${serviceId}`, {
        method: 'DELETE',
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error deleting service:', error);
      throw error;
    }
  }

  async getEvents(appId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/events`, {
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching events:', error);
      throw error;
    }
  }

  async updateEvent(appId, eventId, updateData) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}/events/${eventId}`, {
        method: 'PUT',
        headers: await this.getHeaders(),
        body: JSON.stringify(updateData)
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error updating event:', error);
      throw error;
    }
  }

  async createApplication(applicationData) {
    try {
      const response = await fetch(`${this.baseUrl}/applications`, {
        method: 'POST',
        headers: await this.getHeaders(),
        body: JSON.stringify(applicationData)
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error creating application:', error);
      throw error;
    }
  }

  async updateApplication(appId, updateData) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}`, {
        method: 'PUT',
        headers: await this.getHeaders(),
        body: JSON.stringify(updateData)
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error updating application:', error);
      throw error;
    }
  }

  async deleteApplication(appId) {
    try {
      const response = await fetch(`${this.baseUrl}/applications/${appId}`, {
        method: 'DELETE',
        headers: await this.getHeaders()
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error deleting application:', error);
      throw error;
    }
  }
}

export const applicationService = new ApplicationService();