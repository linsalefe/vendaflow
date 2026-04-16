'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Eye, Loader2, ShoppingCart, DollarSign, TrendingUp, CheckCircle2,
} from 'lucide-react';
import { ColumnDef } from '@tanstack/react-table';
import AppShell from '@/components/app-shell';
import { useAuth } from '@/contexts/auth-context';
import api from '@/lib/api';
import { toast } from 'sonner';
import { PageHeader } from '@/components/ui/page-header';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { TableSkeleton } from '@/components/skeletons/table-skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

interface OrderItem {
  id: number;
  product_name: string;
  variant_label: string | null;
  quantity: number;
  unit_price: string;
  total_price: string;
}

interface Order {
  id: number;
  order_number: string;
  contact_wa_id: string;
  status: string;
  subtotal: string;
  discount_amount: string | null;
  shipping_cost: string | null;
  total: string;
  payment_gateway: string | null;
  payment_link: string | null;
  payment_status: string | null;
  paid_at: string | null;
  tracking_code: string | null;
  coupon_code: string | null;
  notes: string | null;
  created_at: string;
  items?: OrderItem[];
}

interface OrderStats {
  total_orders: number;
  revenue: string;
  paid_orders: number;
  avg_ticket: number;
  by_status: Record<string, number>;
}

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Rascunho' },
  { value: 'pending', label: 'Pendente' },
  { value: 'paid', label: 'Pago' },
  { value: 'processing', label: 'Processando' },
  { value: 'shipped', label: 'Enviado' },
  { value: 'delivered', label: 'Entregue' },
  { value: 'cancelled', label: 'Cancelado' },
  { value: 'refunded', label: 'Reembolsado' },
];

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 border-gray-200',
  pending: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  paid: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  processing: 'bg-blue-50 text-blue-700 border-blue-200',
  shipped: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  delivered: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  cancelled: 'bg-red-50 text-red-700 border-red-200',
  refunded: 'bg-orange-50 text-orange-700 border-orange-200',
};

const PAYMENT_STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  refused: 'bg-red-50 text-red-700 border-red-200',
  refunded: 'bg-orange-50 text-orange-700 border-orange-200',
  expired: 'bg-gray-100 text-gray-700 border-gray-200',
};

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const formatBRL = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? Number(v) : v;
  if (Number.isNaN(n)) return '—';
  return brl.format(n);
};

const formatPhone = (wa_id: string) => {
  const num = wa_id.replace(/^55/, '');
  if (num.length === 11) return `(${num.slice(0, 2)}) ${num.slice(2, 7)}-${num.slice(7)}`;
  return wa_id;
};

const formatDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString('pt-BR') : '—';

const statusLabel = (value: string | null | undefined) =>
  STATUS_OPTIONS.find((s) => s.value === value)?.label ?? value ?? '—';

export default function PedidosPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [orders, setOrders] = useState<Order[]>([]);
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const [detail, setDetail] = useState<Order | null>(null);
  const [editStatus, setEditStatus] = useState<string>('');
  const [editTracking, setEditTracking] = useState<string>('');
  const [editNotes, setEditNotes] = useState<string>('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) loadAll();
  }, [user, statusFilter]);

  const loadAll = async () => {
    try {
      const params = statusFilter !== 'all' ? { status: statusFilter } : {};
      const [ord, st] = await Promise.all([
        api.get('/orders', { params }),
        api.get('/orders/stats'),
      ]);
      setOrders(ord.data);
      setStats(st.data);
    } catch {
      toast.error('Erro ao carregar pedidos');
    } finally {
      setLoading(false);
    }
  };

  const openDetail = async (o: Order) => {
    try {
      const res = await api.get(`/orders/${o.id}`);
      setDetail(res.data);
      setEditStatus(res.data.status || '');
      setEditTracking(res.data.tracking_code || '');
      setEditNotes(res.data.notes || '');
    } catch {
      toast.error('Erro ao carregar detalhes');
    }
  };

  const handleSaveDetail = async () => {
    if (!detail) return;
    setSaving(true);
    try {
      await api.patch(`/orders/${detail.id}`, {
        status: editStatus,
        tracking_code: editTracking || null,
        notes: editNotes || null,
      });
      toast.success('Pedido atualizado');
      setDetail(null);
      loadAll();
    } catch {
      toast.error('Erro ao atualizar pedido');
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnDef<Order>[] = useMemo(() => [
    {
      accessorKey: 'order_number',
      header: 'Nº Pedido',
      cell: ({ row }) => (
        <span className="font-mono text-sm font-medium">#{row.original.order_number}</span>
      ),
    },
    {
      accessorKey: 'contact_wa_id',
      header: 'Cliente',
      cell: ({ row }) => (
        <span className="text-sm">{formatPhone(row.original.contact_wa_id)}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => (
        <Badge
          variant="outline"
          className={STATUS_STYLES[row.original.status] ?? 'bg-gray-100 text-gray-700'}
        >
          {statusLabel(row.original.status)}
        </Badge>
      ),
    },
    {
      accessorKey: 'payment_gateway',
      header: 'Gateway',
      cell: ({ row }) => (
        <span className="capitalize text-sm text-muted-foreground">
          {row.original.payment_gateway ?? '—'}
        </span>
      ),
    },
    {
      accessorKey: 'total',
      header: 'Total',
      cell: ({ row }) => <span className="font-medium">{formatBRL(row.original.total)}</span>,
    },
    {
      accessorKey: 'created_at',
      header: 'Data',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{formatDate(row.original.created_at)}</span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => openDetail(row.original)}
          >
            <Eye className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ], []);

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto pb-10 space-y-6" data-density="medium">
        <PageHeader
          title="Pedidos"
          description="Todos os pedidos gerados pela IA de vendas"
        />

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={ShoppingCart} label="Total Pedidos" value={stats?.total_orders ?? 0} />
          <StatCard
            icon={DollarSign}
            label="Receita Total"
            value={formatBRL(stats?.revenue)}
            tone="emerald"
          />
          <StatCard
            icon={TrendingUp}
            label="Ticket Médio"
            value={formatBRL(stats?.avg_ticket)}
            tone="blue"
          />
          <StatCard
            icon={CheckCircle2}
            label="Pedidos Pagos"
            value={stats?.paid_orders ?? 0}
            tone="emerald"
          />
        </div>

        {/* Filtro de status */}
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground">Status:</Label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {loading ? (
          <TableSkeleton columns={7} rows={8} />
        ) : orders.length === 0 ? (
          <EmptyState
            icon={ShoppingCart}
            title="Nenhum pedido ainda"
            description="Quando a IA concluir vendas no WhatsApp, os pedidos aparecerão aqui."
          />
        ) : (
          <DataTable
            columns={columns}
            data={orders}
            searchPlaceholder="Buscar por número..."
            searchKey="order_number"
          />
        )}
      </div>

      {/* Dialog de detalhes */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Pedido #{detail?.order_number}
            </DialogTitle>
          </DialogHeader>

          {detail && (
            <div className="space-y-5 py-2">
              {/* Resumo */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <InfoRow label="Cliente" value={formatPhone(detail.contact_wa_id)} />
                <InfoRow label="Data" value={formatDate(detail.created_at)} />
                <InfoRow label="Gateway" value={detail.payment_gateway ?? '—'} />
                <InfoRow
                  label="Pagamento"
                  value={
                    detail.payment_status ? (
                      <Badge
                        variant="outline"
                        className={PAYMENT_STATUS_STYLES[detail.payment_status] ?? ''}
                      >
                        {detail.payment_status}
                      </Badge>
                    ) : '—'
                  }
                />
                {detail.paid_at && (
                  <InfoRow label="Pago em" value={formatDate(detail.paid_at)} />
                )}
                {detail.coupon_code && (
                  <InfoRow label="Cupom" value={detail.coupon_code} />
                )}
              </div>

              {detail.payment_link && (
                <div>
                  <Label className="text-xs">Link de pagamento</Label>
                  <a
                    href={detail.payment_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-primary underline break-all"
                  >
                    {detail.payment_link}
                  </a>
                </div>
              )}

              <Separator />

              {/* Items */}
              <div>
                <h4 className="text-sm font-semibold mb-2">Itens</h4>
                <div className="rounded-md border border-border divide-y divide-border">
                  {(detail.items ?? []).map((item) => (
                    <div key={item.id} className="flex items-start justify-between p-3 text-sm">
                      <div>
                        <div className="font-medium">{item.product_name}</div>
                        {item.variant_label && (
                          <div className="text-xs text-muted-foreground">{item.variant_label}</div>
                        )}
                        <div className="text-xs text-muted-foreground mt-1">
                          {item.quantity} × {formatBRL(item.unit_price)}
                        </div>
                      </div>
                      <div className="font-medium">{formatBRL(item.total_price)}</div>
                    </div>
                  ))}
                  {(!detail.items || detail.items.length === 0) && (
                    <div className="p-3 text-sm text-muted-foreground text-center">
                      Sem itens
                    </div>
                  )}
                </div>
              </div>

              {/* Totais */}
              <div className="space-y-1.5 text-sm">
                <InfoRow label="Subtotal" value={formatBRL(detail.subtotal)} />
                {detail.discount_amount && Number(detail.discount_amount) > 0 && (
                  <InfoRow label="Desconto" value={`- ${formatBRL(detail.discount_amount)}`} />
                )}
                {detail.shipping_cost && Number(detail.shipping_cost) > 0 && (
                  <InfoRow label="Frete" value={formatBRL(detail.shipping_cost)} />
                )}
                <Separator />
                <div className="flex justify-between font-semibold text-base">
                  <span>Total</span>
                  <span>{formatBRL(detail.total)}</span>
                </div>
              </div>

              <Separator />

              {/* Edição */}
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Status do pedido</Label>
                  <Select value={editStatus} onValueChange={setEditStatus}>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Código de rastreio</Label>
                  <Input
                    value={editTracking}
                    onChange={(e) => setEditTracking(e.target.value)}
                    placeholder="Ex: BR123456789"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Notas internas</Label>
                  <Textarea
                    rows={2}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)}>Fechar</Button>
            <Button onClick={handleSaveDetail} disabled={saving || !detail}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  tone?: 'emerald' | 'blue';
}) {
  const toneCls =
    tone === 'emerald'
      ? 'text-emerald-600 bg-emerald-50'
      : tone === 'blue'
      ? 'text-blue-600 bg-blue-50'
      : 'text-primary bg-primary/10';
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${toneCls}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-muted-foreground text-xs uppercase tracking-wide">{label}</span>
      <span className="font-medium text-sm">{value}</span>
    </div>
  );
}
