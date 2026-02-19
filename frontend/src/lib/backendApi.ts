import { AuthService } from './auth';
import { BidSearchParams, BidApiResponse, BidAValueApiResponse, BidAValueItem, BidItem, PrtcptPsblRgnItem, UserLocation, BookmarkWithStatus, BidResultResponse, BusinessProfile } from '@/types/bid';

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
  bid_notice_ord?: string;
  status: string;
  bid_price?: number;
  notes?: string;
  created_at: string;
  updated_at?: string;
}

class BackendApiService {
  private getAuthHeaders(): HeadersInit {
    const token = AuthService.getToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };
  }

  private async authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const response = await fetch(input, init);
    if (response.status === 401) {
      AuthService.triggerExpired();
    }
    return response;
  }

  async searchBids(params: BidSearchParams): Promise<BidApiResponse> {
    // Backend handles comma-separated regions/industries in a single query
    return this.fetchSingleSearch(params);
  }

  private async fetchSingleSearch(params: BidSearchParams): Promise<BidApiResponse> {
    const searchParams = {
      inqryDiv: params.inqryDiv,
      inqryBgnDt: params.inqryBgnDt,
      inqryEndDt: params.inqryEndDt,
      prtcptLmtRgnNm: params.prtcptLmtRgnNm,
      cnstrtsiteRgnNm: params.cnstrtsiteRgnNm,
      indstrytyNm: params.indstrytyNm,
      presmptPrceBgn: params.presmptPrceBgn,
      presmptPrceEnd: params.presmptPrceEnd,
      bidClseExcpYn: params.bidClseExcpYn,
      useLocationFilter: params.useLocationFilter,
      orderBy: params.orderBy,
      orderDir: params.orderDir,
      numOfRows: params.numOfRows || 100,
      pageNo: params.pageNo || 1,
    };

    const response = await this.authFetch(`${API_BASE_URL}/bids/search`, {
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

  async getBidDetail(bidNtceNo: string, bidNtceOrd: string = '000'): Promise<BidItem | null> {
    const url = new URL(`${window.location.origin}${API_BASE_URL}/bids/${bidNtceNo}/detail`);
    url.searchParams.append('bidNtceOrd', bidNtceOrd);

    const response = await this.authFetch(url.toString(), {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (response.status === 404) return null;
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '공고 상세 조회 실패');
    }
    return response.json();
  }

  async getBidAValue(bidNtceNo: string, bidType: string = 'cnstwk'): Promise<BidAValueItem | null> {
    // bid_type을 쿼리 스트링으로 추가합니다.
    const url = new URL(`${window.location.origin}${API_BASE_URL}/bids/a-value/${bidNtceNo}/`);
    url.searchParams.append('bid_type', bidType);

    const response = await this.authFetch(url.toString(), {
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
    const response = await this.authFetch(`${API_BASE_URL}/preferences`, {
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
    const response = await this.authFetch(`${API_BASE_URL}/preferences`, {
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
    const response = await this.authFetch(`${API_BASE_URL}/preferences/searches`, {
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
    const response = await this.authFetch(`${API_BASE_URL}/preferences/searches`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get saved searches');
    }

    return response.json();
  }

  async deleteSavedSearch(searchId: string): Promise<void> {
    const response = await this.authFetch(`${API_BASE_URL}/preferences/searches/${searchId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete saved search');
    }
  }

  async createBookmark(
    bidNoticeNo: string,
    bidNoticeName: string,
    options?: { notes?: string; status?: string; bid_price?: number; bid_notice_ord?: string }
  ): Promise<Bookmark> {
    const response = await this.authFetch(`${API_BASE_URL}/bids/bookmarks`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        bid_notice_no: bidNoticeNo,
        bid_notice_name: bidNoticeName,
        bid_notice_ord: options?.bid_notice_ord,
        status: options?.status || 'interested',
        bid_price: options?.bid_price,
        notes: options?.notes,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create bookmark');
    }

    return response.json();
  }

  async getBookmarks(status?: string): Promise<BookmarkWithStatus[]> {
    const url = status
      ? `${API_BASE_URL}/bids/bookmarks?bookmark_status=${status}`
      : `${API_BASE_URL}/bids/bookmarks`;
    const response = await this.authFetch(url, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get bookmarks');
    }

    return response.json();
  }

  async updateBookmark(
    bookmarkId: string,
    data: { status?: string; bid_price?: number; notes?: string }
  ): Promise<BookmarkWithStatus> {
    const response = await this.authFetch(`${API_BASE_URL}/bids/bookmarks/${bookmarkId}`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update bookmark');
    }

    return response.json();
  }

  async deleteBookmark(bookmarkId: string): Promise<void> {
    const response = await this.authFetch(`${API_BASE_URL}/bids/bookmarks/${bookmarkId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete bookmark');
    }
  }

  // --- Bid Results API ---

  async getBidResults(bidNtceNo: string): Promise<BidResultResponse> {
    const response = await this.authFetch(`${API_BASE_URL}/bids/${bidNtceNo}/results`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '개찰결과 조회 실패');
    }

    return response.json();
  }

  // --- Business Profile API ---

  async getBusinessProfile(): Promise<BusinessProfile | null> {
    const response = await this.authFetch(`${API_BASE_URL}/profile/business`, {
      headers: this.getAuthHeaders(),
    });

    if (response.status === 404) return null;

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '사업자정보 조회 실패');
    }

    return response.json();
  }

  async updateBusinessProfile(data: Partial<BusinessProfile>): Promise<BusinessProfile> {
    const response = await this.authFetch(`${API_BASE_URL}/profile/business`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '사업자정보 수정 실패');
    }

    return response.json();
  }

  // --- Location API ---

  async getLocation(): Promise<UserLocation | null> {
    const response = await this.authFetch(`${API_BASE_URL}/locations`, {
      headers: this.getAuthHeaders(),
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '소재지 조회 실패');
    }

    return response.json();
  }

  async setLocation(locationName: string): Promise<UserLocation> {
    const response = await this.authFetch(`${API_BASE_URL}/locations`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ location_name: locationName }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '소재지 등록 실패');
    }

    return response.json();
  }

  async deleteLocation(): Promise<void> {
    const response = await this.authFetch(`${API_BASE_URL}/locations`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '소재지 삭제 실패');
    }
  }

  // --- Regions API ---

  async getBidRegions(bidNtceNo: string, bidNtceOrd: string = '000'): Promise<PrtcptPsblRgnItem[]> {
    const url = new URL(`${window.location.origin}${API_BASE_URL}/bids/${bidNtceNo}/regions`);
    url.searchParams.append('bidNtceOrd', bidNtceOrd);

    const response = await this.authFetch(url.toString(), {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  // --- Sync API ---

  async triggerSync(days: number = 30): Promise<void> {
    const response = await this.authFetch(`${API_BASE_URL}/bids/sync?days=${days}`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '동기화 실패');
    }
  }
}

export const backendApi = new BackendApiService();
