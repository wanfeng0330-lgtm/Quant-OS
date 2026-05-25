import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'https://quant-os-production.up.railway.app/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // You can add auth tokens here
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // Handle common errors
    if (error.response) {
      const { status, data } = error.response
      const errorMessage = data?.message || data?.error || 'Unknown error'

      switch (status) {
        case 400:
          console.error('Bad Request:', errorMessage)
          break
        case 401:
          console.error('Unauthorized:', errorMessage)
          break
        case 403:
          console.error('Forbidden:', errorMessage)
          break
        case 404:
          console.error('Not Found:', errorMessage)
          break
        case 429:
          console.error('Rate Limited:', errorMessage)
          break
        case 500:
          console.error('Server Error:', errorMessage)
          break
      }
    } else if (error.request) {
      console.error('Network Error: No response received')
    } else {
      console.error('Request Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export default apiClient