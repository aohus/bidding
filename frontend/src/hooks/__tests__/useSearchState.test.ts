import { renderHook, act } from '@testing-library/react-hooks';
import { useSearchState } from '../useSearchState';

describe('useSearchState', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should initialize with default values', () => {
    const { result } = renderHook(() => useSearchState());
    expect(result.current.searchParams).toEqual(null);
    expect(result.current.bids).toEqual([]);
  });

  it('should load state from localStorage on initialization', () => {
    const mockParams = { inqryBgnDt: '20230101' };
    localStorage.setItem('searchParams', JSON.stringify(mockParams));
    
    const { result } = renderHook(() => useSearchState());
    expect(result.current.searchParams).toEqual(mockParams);
  });

  it('should save search params to localStorage', () => {
    const { result } = renderHook(() => useSearchState());
    const newParams = { inqryBgnDt: '20230201' };
    
    act(() => {
      result.current.setSearchParams(newParams);
    });
    
    expect(localStorage.getItem('searchParams')).toEqual(JSON.stringify(newParams));
  });
});
