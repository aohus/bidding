import { useState, useEffect } from 'react';
import { AuthService } from '@/lib/auth';
import { backendApi } from '@/lib/backendApi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Settings as SettingsIcon, Save } from 'lucide-react';
import { toast } from 'sonner';
import Header from '@/components/Header';
import { useNavigate } from 'react-router-dom';
import { BusinessProfile } from '@/types/bid';

export default function Settings() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<BusinessProfile>({
    business_number: null,
    company_name: null,
    representative_name: null,
  });

  useEffect(() => {
    AuthService.setOnExpired(() => navigate('/'));
    return () => AuthService.setOnExpired(null);
  }, [navigate]);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await backendApi.getBusinessProfile();
      if (data) {
        setForm(data);
      }
    } catch (error) {
      // Profile may not exist yet
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await backendApi.updateBusinessProfile(form);
      toast.success('사업자정보가 저장되었습니다');
    } catch (error) {
      toast.error('저장에 실패했습니다');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={() => navigate('/')} />

      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <div className="mb-6 flex items-center gap-3">
          <SettingsIcon className="h-8 w-8 text-blue-600" />
          <div>
            <h2 className="text-3xl font-bold text-gray-900">정보수정</h2>
            <p className="text-sm text-gray-600 mt-1">
              사업자 정보를 등록하면 개찰결과에서 자동으로 내 투찰정보를 확인할 수 있습니다
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
          </div>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">사업자 정보</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="business_number">사업자등록번호</Label>
                <Input
                  id="business_number"
                  placeholder="000-00-00000"
                  value={form.business_number || ''}
                  onChange={(e) =>
                    setForm({ ...form, business_number: e.target.value || null })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company_name">업체명</Label>
                <Input
                  id="company_name"
                  placeholder="업체명을 입력하세요"
                  value={form.company_name || ''}
                  onChange={(e) =>
                    setForm({ ...form, company_name: e.target.value || null })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="representative_name">대표자명</Label>
                <Input
                  id="representative_name"
                  placeholder="대표자명을 입력하세요"
                  value={form.representative_name || ''}
                  onChange={(e) =>
                    setForm({ ...form, representative_name: e.target.value || null })
                  }
                />
              </div>
              <div className="pt-4">
                <Button onClick={handleSave} disabled={saving} className="w-full">
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? '저장 중...' : '저장'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
