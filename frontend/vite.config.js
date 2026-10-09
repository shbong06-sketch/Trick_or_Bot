// 개발 서버(5173)에서 게임 서버(FastAPI, 8000)로 API·WebSocket을 넘긴다
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
};
