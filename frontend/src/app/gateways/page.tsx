'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  CreditCard, Loader2, CheckCircle, XCircle, Zap, ShieldCheck,
} from 'lucide-react';
import AppShell from '@/components/app-shell';
import { useAuth } from '@/contexts/auth-context';
import api from '@/lib/api';
import { toast } from 'sonner';
import { PageHeader } from '@/components/ui/page-header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

interface GatewayState {
  default_gateway: string | null;
  stripe_secret_key: string | null;
  stripe_webhook_secret: string | null;
  hotmart_token: string | null;
  hotmart_hottok: string | null;
  kiwify_api_key: string | null;
  kiwify_webhook_secret: string | null;
  mercadopago_access_token: string | null;
  mercadopago_webhook_secret: string | null;
}

type GatewayKey = 'stripe' | 'hotmart' | 'kiwify' | 'mercadopago';

interface GatewayField {
  key: keyof GatewayState;
  label: string;
  placeholder: string;
}

interface GatewayDef {
  key: GatewayKey;
  name: string;
  description: string;
  fields: GatewayField[];
}

const GATEWAYS: GatewayDef[] = [
  {
    key: 'stripe',
    name: 'Stripe',
    description: 'Cartão internacional, Apple/Google Pay, PIX',
    fields: [
      { key: 'stripe_secret_key', label: 'Secret Key', placeholder: 'sk_live_...' },
      { key: 'stripe_webhook_secret', label: 'Webhook Secret', placeholder: 'whsec_...' },
    ],
  },
  {
    key: 'hotmart',
    name: 'Hotmart',
    description: 'Marketplace de infoprodutos',
    fields: [
      { key: 'hotmart_token', label: 'Token de acesso', placeholder: 'Bearer token' },
      { key: 'hotmart_hottok', label: 'Hottok (webhook)', placeholder: 'hottok_...' },
    ],
  },
  {
    key: 'kiwify',
    name: 'Kiwify',
    description: 'Plataforma de produtos digitais',
    fields: [
      { key: 'kiwify_api_key', label: 'API Key', placeholder: 'kwfy_...' },
      { key: 'kiwify_webhook_secret', label: 'Webhook Secret', placeholder: 'webhook_secret' },
    ],
  },
  {
    key: 'mercadopago',
    name: 'MercadoPago',
    description: 'PIX, boleto, cartão nacional',
    fields: [
      { key: 'mercadopago_access_token', label: 'Access Token', placeholder: 'APP_USR-...' },
      { key: 'mercadopago_webhook_secret', label: 'Webhook Secret', placeholder: 'webhook_secret' },
    ],
  },
];

export default function GatewaysPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [state, setState] = useState<GatewayState | null>(null);
  const [loading, setLoading] = useState(true);
  const [defaultGateway, setDefaultGateway] = useState<string>('stripe');
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [savingDefault, setSavingDefault] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) loadConfig();
  }, [user]);

  const loadConfig = async () => {
    try {
      const res = await api.get('/gateways');
      setState(res.data);
      setDefaultGateway(res.data.default_gateway || 'stripe');
    } catch (e: any) {
      if (e.response?.status === 403) {
        toast.error('Apenas administradores podem acessar esta página');
        router.push('/dashboard');
      } else {
        toast.error('Erro ao carregar configurações');
      }
    } finally {
      setLoading(false);
    }
  };

  const isConfigured = (gw: GatewayDef): boolean =>
    gw.fields.some((f) => !!state?.[f.key]);

  const saveGateway = async (gw: GatewayDef) => {
    const payload: Record<string, string> = {};
    gw.fields.forEach((f) => {
      const v = fieldValues[f.key as string];
      if (v && v.trim()) payload[f.key as string] = v.trim();
    });

    if (Object.keys(payload).length === 0) {
      return toast.error('Preencha ao menos um campo para salvar');
    }

    setSaving((s) => ({ ...s, [gw.key]: true }));
    try {
      const res = await api.patch('/gateways', payload);
      setState(res.data);
      const clear: Record<string, string> = { ...fieldValues };
      gw.fields.forEach((f) => { clear[f.key as string] = ''; });
      setFieldValues(clear);
      toast.success(`${gw.name} atualizado`);
    } catch {
      toast.error(`Erro ao salvar ${gw.name}`);
    } finally {
      setSaving((s) => ({ ...s, [gw.key]: false }));
    }
  };

  const testGateway = async (gw: GatewayDef) => {
    setTesting((t) => ({ ...t, [gw.key]: true }));
    try {
      const res = await api.post('/gateways/test', { gateway: gw.key });
      if (res.data.ok) {
        toast.success(`${gw.name}: ${res.data.message ?? 'Conexão OK'}`);
      } else {
        toast.error(`${gw.name}: ${res.data.message ?? 'Falhou'}`);
      }
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? `Erro ao testar ${gw.name}`);
    } finally {
      setTesting((t) => ({ ...t, [gw.key]: false }));
    }
  };

  const saveDefaultGateway = async () => {
    setSavingDefault(true);
    try {
      const res = await api.patch('/gateways', { default_gateway: defaultGateway });
      setState(res.data);
      toast.success('Gateway padrão atualizado');
    } catch {
      toast.error('Erro ao atualizar gateway padrão');
    } finally {
      setSavingDefault(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto pb-10 space-y-6" data-density="medium">
        <PageHeader
          title="Gateways de Pagamento"
          description="Configure os gateways que a IA pode usar para gerar links de pagamento"
        />

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-60 w-full" />
            <Skeleton className="h-60 w-full" />
          </div>
        ) : (
          <>
            {/* Gateway padrão */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Zap className="h-4 w-4 text-primary" />
                  Gateway padrão
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-end gap-3">
                <div className="flex-1 max-w-xs space-y-1.5">
                  <Label className="text-xs">Usado quando o produto não especifica</Label>
                  <Select value={defaultGateway} onValueChange={setDefaultGateway}>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {GATEWAYS.map((g) => (
                        <SelectItem key={g.key} value={g.key}>{g.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={saveDefaultGateway} disabled={savingDefault}>
                  {savingDefault ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                  Salvar
                </Button>
              </CardContent>
            </Card>

            {/* Cards por gateway */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {GATEWAYS.map((gw) => {
                const configured = isConfigured(gw);
                const isDefault = state?.default_gateway === gw.key;
                return (
                  <Card key={gw.key}>
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-3">
                          <div className="h-10 w-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                            <CreditCard className="h-5 w-5" />
                          </div>
                          <div>
                            <CardTitle className="text-base">{gw.name}</CardTitle>
                            <p className="text-xs text-muted-foreground mt-0.5">{gw.description}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          {configured ? (
                            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                              <CheckCircle className="h-3 w-3 mr-1" />
                              Configurado
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-gray-100 text-gray-600 border-gray-200">
                              <XCircle className="h-3 w-3 mr-1" />
                              Não configurado
                            </Badge>
                          )}
                          {isDefault && (
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                              <ShieldCheck className="h-3 w-3 mr-1" />
                              Padrão
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-3">
                      {gw.fields.map((f) => {
                        const existing = state?.[f.key];
                        return (
                          <div key={f.key as string} className="space-y-1.5">
                            <Label className="text-xs">{f.label}</Label>
                            <Input
                              type="password"
                              autoComplete="off"
                              value={fieldValues[f.key as string] ?? ''}
                              onChange={(e) =>
                                setFieldValues((v) => ({ ...v, [f.key as string]: e.target.value }))
                              }
                              placeholder={existing ? (existing as string) : f.placeholder}
                            />
                            {existing && (
                              <p className="text-[11px] text-muted-foreground">
                                Atual: <span className="font-mono">{existing}</span> — deixe em branco para manter
                              </p>
                            )}
                          </div>
                        );
                      })}

                      <div className="flex items-center gap-2 pt-2">
                        <Button
                          onClick={() => saveGateway(gw)}
                          disabled={saving[gw.key]}
                          className="flex-1"
                        >
                          {saving[gw.key]
                            ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            : <CheckCircle className="h-4 w-4 mr-2" />}
                          Salvar
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => testGateway(gw)}
                          disabled={!configured || testing[gw.key]}
                          className="flex-1"
                        >
                          {testing[gw.key]
                            ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            : <Zap className="h-4 w-4 mr-2" />}
                          Testar
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
