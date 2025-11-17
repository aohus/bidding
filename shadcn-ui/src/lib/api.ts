import { BidSearchParams, BidApiResponse } from '@/types/bid';

const API_BASE_URL = '/api/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch';

export async function searchBids(params: BidSearchParams): Promise<BidApiResponse> {
  const queryParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      queryParams.append(key, String(value));
    }
  });

  queryParams.append('type', 'json');

  try {
    const response = await fetch(`${API_BASE_URL}?${queryParams.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`API 요청 실패: ${response.status}`);
    }

    const data: BidApiResponse = await response.json();
    
    if (data.response.header.resultCode !== '00') {
      throw new Error(data.response.header.resultMsg || 'API 오류');
    }

    return data;
  } catch (error) {
    console.error('API 호출 오류:', error);
    throw error;
  }
}

export function downloadDocument(url: string, filename: string) {
  if (!url) return;
  
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}