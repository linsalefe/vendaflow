'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus, Pencil, Trash2, Loader2, CheckCircle, Ticket,
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
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import ConfirmModal from '@/components/ConfirmModal';

interface Coupon {
  id: number;
  code: string;
  discount_type: string;
  discount_value: string;
  min_order_value: string | null;
  max_uses: number | null;
  used_count: number;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const formatBRL = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? Number(v) : v;
  if (Number.isNaN(n)) return '—';
  return brl.format(n);
};

const formatDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString('pt-BR') : '—';

const toInputDate = (d: string | null) => (d ? d.slice(0, 10) : '');

const emptyForm = {
  code: '',
  discount_type: 'percentage',
  discount_value: '',
  min_order_value: '',
  max_uses: '',
  is_active: true,
  expires_at: '',
};

export default function CuponsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Coupon | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Coupon | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) loadCoupons();
  }, [user]);

  const loadCoupons = async () => {
    try {
      const res = await api.get('/coupons');
      setCoupons(res.data);
    } catch {
      toast.error('Erro ao carregar cupons');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setShowModal(true);
  };

  const openEdit = (c: Coupon) => {
    setEditing(c);
    setForm({
      code: c.code,
      discount_type: c.discount_type,
      discount_value: c.discount_value,
      min_order_value: c.min_order_value ?? '',
      max_uses: c.max_uses != null ? String(c.max_uses) : '',
      is_active: c.is_active,
      expires_at: toInputDate(c.expires_at),
    });
    setShowModal(true);
  };

  const isExpired = (c: Coupon) =>
    !!c.expires_at && new Date(c.expires_at).getTime() < Date.now();

  const handleSave = async () => {
    if (!form.code.trim()) return toast.error('Código é obrigatório');
    if (!form.discount_value || Number(form.discount_value) <= 0)
      return toast.error('Valor do desconto é obrigatório');

    const payload: Record<string, unknown> = {
      code: form.code.trim().toUpperCase(),
      discount_type: form.discount_type,
      discount_value: Number(form.discount_value),
      is_active: form.is_active,
    };

    if (form.min_order_value) payload.min_order_value = Number(form.min_order_value);
    if (form.max_uses) payload.max_uses = Number(form.max_uses);
    if (form.expires_at) payload.expires_at = new Date(form.expires_at).toISOString();

    setSaving(true);
    try {
      if (editing) {
        await api.patch(`/coupons/${editing.id}`, payload);
        toast.success('Cupom atualizado');
      } else {
        await api.post('/coupons', payload);
        toast.success('Cupom criado');
      }
      setShowModal(false);
      loadCoupons();
    } catch {
      toast.error('Erro ao salvar cupom');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/coupons/${deleteTarget.id}`);
      toast.success('Cupom removido');
      setDeleteTarget(null);
      loadCoupons();
    } catch {
      toast.error('Erro ao remover cupom');
    } finally {
      setDeleting(false);
    }
  };

  const columns: ColumnDef<Coupon>[] = useMemo(() => [
    {
      accessorKey: 'code',
      header: 'Código',
      cell: ({ row }) => (
        <span className="font-mono text-sm font-semibold">{row.original.code}</span>
      ),
    },
    {
      accessorKey: 'discount_type',
      header: 'Tipo',
      cell: ({ row }) => (
        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
          {row.original.discount_type === 'percentage' ? 'Percentual' : 'Fixo'}
        </Badge>
      ),
    },
    {
      accessorKey: 'discount_value',
      header: 'Valor',
      cell: ({ row }) => {
        const c = row.original;
        return c.discount_type === 'percentage'
          ? <span className="font-medium">{Number(c.discount_value)}%</span>
          : <span className="font-medium">{formatBRL(c.discount_value)}</span>;
      },
    },
    {
      id: 'uses',
      header: 'Uso',
      cell: ({ row }) => {
        const c = row.original;
        return (
          <span className="text-sm">
            {c.used_count}{c.max_uses != null ? ` / ${c.max_uses}` : ''}
          </span>
        );
      },
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const c = row.original;
        if (!c.is_active) {
          return <Badge variant="outline" className="bg-gray-100 text-gray-700 border-gray-200">Inativo</Badge>;
        }
        if (isExpired(c)) {
          return <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-200">Expirado</Badge>;
        }
        return <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">Ativo</Badge>;
      },
    },
    {
      accessorKey: 'expires_at',
      header: 'Validade',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {formatDate(row.original.expires_at)}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex items-center gap-1 justify-end">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-primary"
            onClick={() => openEdit(row.original)}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
            onClick={() => setDeleteTarget(row.original)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ], []);

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto pb-10 space-y-6" data-density="medium">
        <PageHeader
          title="Cupons"
          description="Códigos de desconto que a IA pode aplicar no checkout"
          actions={
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Novo Cupom
            </Button>
          }
        />

        {loading ? (
          <TableSkeleton columns={7} rows={6} />
        ) : coupons.length === 0 ? (
          <EmptyState
            icon={Ticket}
            title="Nenhum cupom criado"
            description="Crie códigos promocionais para oferecer descontos aos seus clientes."
            actionLabel="Criar Primeiro Cupom"
            onAction={openCreate}
          />
        ) : (
          <DataTable
            columns={columns}
            data={coupons}
            searchPlaceholder="Buscar por código..."
            searchKey="code"
          />
        )}
      </div>

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar cupom' : 'Novo cupom'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Código *</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                placeholder="PROMO10"
                className="font-mono uppercase"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Tipo *</Label>
                <Select
                  value={form.discount_type}
                  onValueChange={(v) => setForm({ ...form, discount_type: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">Percentual (%)</SelectItem>
                    <SelectItem value="fixed">Fixo (R$)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">
                  Valor * {form.discount_type === 'percentage' ? '(%)' : '(R$)'}
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.discount_value}
                  onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Valor mínimo (R$)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.min_order_value}
                  onChange={(e) => setForm({ ...form, min_order_value: e.target.value })}
                  placeholder="Opcional"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Limite de usos</Label>
                <Input
                  type="number"
                  value={form.max_uses}
                  onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
                  placeholder="Sem limite"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Validade</Label>
              <Input
                type="date"
                value={form.expires_at}
                onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
              />
            </div>

            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <div>
                <div className="text-sm font-medium">Ativo</div>
                <div className="text-xs text-muted-foreground">
                  Cupons inativos não podem ser usados
                </div>
              </div>
              <Switch
                checked={form.is_active}
                onCheckedChange={(v) => setForm({ ...form, is_active: v })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
              {editing ? 'Salvar' : 'Criar cupom'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmModal
        open={!!deleteTarget}
        title="Excluir cupom"
        message={`Tem certeza que deseja excluir o cupom ${deleteTarget?.code ?? ''}?`}
        confirmLabel={deleting ? 'Excluindo...' : 'Excluir'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        variant="danger"
      />
    </AppShell>
  );
}
