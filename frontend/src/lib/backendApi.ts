import { AuthService } from './auth';
import { BidSearchParams, BidApiResponse, BidAValueApiResponse, BidAValueItem } from '@/types/bid';

const API_BASE_URL = '/server';

interface UserPreference {
  preference_id: string;
  user_id: string;
  search_conditions: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface SavedSearch {
  search_id: string;
  user_id: string;
  search_name: string;
  filters: Record<string, unknown>;
  created_at: string;
}

interface Bookmark {
  bookmark_id: string;
  user_id: string;
  bid_notice_no: string;
  bid_notice_name: string;
  notes?: string;
  created_at: string;
}

class BackendApiService {
  private getAuthHeaders(): HeadersInit {
    const token = AuthService.getToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };
  }

  async searchBids(params: BidSearchParams): Promise<BidApiResponse> {
    // Split comma-separated values (handle potential spaces)
    const regions = params.prtcptLmtRgnNm 
      ? params.prtcptLmtRgnNm.split(',').map(s => s.trim()).filter(s => s) 
      : [undefined];
    const industries = params.indstrytyNm 
      ? params.indstrytyNm.split(',').map(s => s.trim()).filter(s => s) 
      : [undefined];

    // If single request, use direct call
    if (regions.length <= 1 && industries.length <= 1) {
      // Ensure we pass the single value (or undefined) correctly
      const singleParams = {
        ...params,
        prtcptLmtRgnNm: regions[0],
        indstrytyNm: industries[0],
      };
      return this.fetchSingleSearch(singleParams);
    }

    // Create combinations for multiple requests
    const combinations: BidSearchParams[] = [];
    for (const region of regions) {
      for (const industry of industries) {
        combinations.push({
          ...params,
          prtcptLmtRgnNm: region,
          indstrytyNm: industry,
        });
      }
    }

    // Execute parallel requests
    const responses = await Promise.all(combinations.map(p => this.fetchSingleSearch(p)));

    // Merge results
    const mergedItems: any[] = [];
    const seenIds = new Set();
    let approximateTotalCount = 0;

    for (const res of responses) {
      approximateTotalCount += res.response.body.totalCount || 0;
      const items = res.response.body.items || [];
      for (const item of items) {
        if (!seenIds.has(item.bidNtceNo)) {
          seenIds.add(item.bidNtceNo);
          mergedItems.push(item);
        }
      }
    }

    // Sort merged results by registration date (descending)
    mergedItems.sort((a, b) => {
      // Assuming rgstDt format YYYY-MM-DD HH:MM:SS or similar sortable string
      if (!a.rgstDt) return 1;
      if (!b.rgstDt) return -1;
      return b.rgstDt.localeCompare(a.rgstDt);
    });

    return {
      response: {
        header: {
          resultCode: '00',
          resultMsg: 'SUCCESS',
        },
        body: {
          items: mergedItems,
          numOfRows: params.numOfRows || 100,
          pageNo: params.pageNo || 1,
          totalCount: approximateTotalCount, // Approximation
        },
      },
    };
  }

  private async fetchSingleSearch(params: BidSearchParams): Promise<BidApiResponse> {
    const searchParams = {
      inqryDiv: params.inqryDiv,
      inqryBgnDt: params.inqryBgnDt,
      inqryEndDt: params.inqryEndDt,
      prtcptLmtRgnCd: params.prtcptLmtRgnCd,
      prtcptLmtRgnNm: params.prtcptLmtRgnNm,
      indstrytyNm: params.indstrytyNm,
      presmptPrceBgn: params.presmptPrceBgn,
      presmptPrceEnd: params.presmptPrceEnd,
      bidClseExcpYn: params.bidClseExcpYn,
      numOfRows: params.numOfRows || 100,
      pageNo: params.pageNo || 1,
    };

    const response = await fetch(`${API_BASE_URL}/bids/search`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(searchParams),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Search failed');
    }

    const data = await response.json();
    
    // Transform backend response to frontend format
    return {
      response: {
        header: {
          resultCode: '00',
          resultMsg: 'SUCCESS',
        },
        body: {
          items: data.items || [],
          numOfRows: data.numOfRows,
          pageNo: data.pageNo,
          totalCount: data.totalCount,
        },
      },
    };
  }

  async getBidAValue(bidNtceNo: string, bidType: string = 'cnstwk'): Promise<BidAValueItem | null> {
    // bid_type을 쿼리 스트링으로 추가합니다.
    const url = new URL(`${window.location.origin}${API_BASE_URL}/bids/a-value/${bidNtceNo}/`);
    url.searchParams.append('bid_type', bidType);

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'A값 조회 실패');
    }

    const data = await response.json();
    // 백엔드에서 BidAValueItem 객체를 바로 반환한다고 가정합니다.
    return data;
  }

  async savePreference(searchConditions: Record<string, unknown>): Promise<UserPreference> {
    const response = await fetch(`${API_BASE_URL}/preferences`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ search_conditions: searchConditions }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to save preference');
    }

    return response.json();
  }

  async getPreference(): Promise<UserPreference | null> {
    const response = await fetch(`${API_BASE_URL}/preferences`, {
      headers: this.getAuthHeaders(),
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get preference');
    }

    return response.json();
  }

  async createSavedSearch(searchName: string, filters: Record<string, unknown>): Promise<SavedSearch> {
    const response = await fetch(`${API_BASE_URL}/preferences/searches`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ search_name: searchName, filters }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create saved search');
    }

    return response.json();
  }

  async getSavedSearches(): Promise<SavedSearch[]> {
    const response = await fetch(`${API_BASE_URL}/preferences/searches`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get saved searches');
    }

    return response.json();
  }

  async deleteSavedSearch(searchId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/preferences/searches/${searchId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete saved search');
    }
  }

  async createBookmark(bidNoticeNo: string, bidNoticeName: string, notes?: string): Promise<Bookmark> {
    const response = await fetch(`${API_BASE_URL}/bookmarks`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ bid_notice_no: bidNoticeNo, bid_notice_name: bidNoticeName, notes }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create bookmark');
    }

    return response.json();
  }

  async getBookmarks(): Promise<Bookmark[]> {
    const response = await fetch(`${API_BASE_URL}/bookmarks`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get bookmarks');
    }

    return response.json();
  }

  async deleteBookmark(bookmarkId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/bookmarks/${bookmarkId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete bookmark');
    }
  }
}

export const backendApi = new BackendApiService();
