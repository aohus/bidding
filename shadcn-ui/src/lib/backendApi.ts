import { AuthService } from './auth';
import { BidSearchParams, BidApiResponse } from '@/types/bid';

const API_BASE_URL = 'http://localhost:8000/api';

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
    const searchParams = {
      inqry_div: params.inqryDiv,
      inqry_bgn_dt: params.inqryBgnDt,
      inqry_end_dt: params.inqryEndDt,
      prtcpt_lmt_rgn_cd: params.prtcptLmtRgnCd,
      presmpt_prce_bgn: params.presmptPrceBgn,
      presmpt_prce_end: params.presmptPrceEnd,
      num_of_rows: params.numOfRows || 100,
      page_no: params.pageNo || 1,
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
          numOfRows: data.num_of_rows,
          pageNo: data.page_no,
          totalCount: data.total_count,
        },
      },
    };
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
    const response = await fetch(`${API_BASE_URL}/saved-searches`, {
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
    const response = await fetch(`${API_BASE_URL}/saved-searches`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get saved searches');
    }

    return response.json();
  }

  async deleteSavedSearch(searchId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/saved-searches/${searchId}`, {
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