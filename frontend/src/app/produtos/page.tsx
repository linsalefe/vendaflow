'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus, Package, Pencil, Trash2, Loader2, CheckCircle, Tag, Box, AlertTriangle,
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
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import ConfirmModal from '@/components/ConfirmModal';

interface Product {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  short_description: string | null;
  product_type: string;
  price: string;
  compare_at_price: string | null;
  wholesale_price: string | null;
  wholesale_min_qty: number | null;
  cost_price: string | null;
  category_id: number | null;
  track_stock: boolean;
  stock_quantity: number;
  low_stock_alert: number | null;
  image_url: string | null;
  ai_selling_points: string | null;
  search_tags: string[];
  is_active: boolean;
  is_featured: boolean;
}

interface Category {
  id: number;
  name: string;
  slug: string;
}

interface ProductStats {
  total: number;
  active: number;
  out_of_stock: number;
  stock_units: number;
  stock_value: string;
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const formatBRL = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? Number(v) : v;
  if (Number.isNaN(n)) return '—';
  return brl.format(n);
};

const emptyForm = {
  name: '',
  short_description: '',
  description: '',
  product_type: 'physical',
  category_id: '',
  price: '',
  compare_at_price: '',
  wholesale_price: '',
  wholesale_min_qty: '',
  cost_price: '',
  track_stock: true,
  stock_quantity: '',
  low_stock_alert: '',
  image_url: '',
  ai_selling_points: '',
  search_tags: '',
};

export default function ProdutosPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [stats, setStats] = useState<ProductStats | null>(null);
  const [loading, setLoading] = useState(true);

  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) loadAll();
  }, [user]);

  const loadAll = async () => {
    try {
      const [prods, cats, st] = await Promise.all([
        api.get('/products'),
        api.get('/products/categories'),
        api.get('/products/stats'),
      ]);
      setProducts(prods.data);
      setCategories(cats.data);
      setStats(st.data);
    } catch {
      toast.error('Erro ao carregar produtos');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setShowModal(true);
  };

  const openEdit = (p: Product) => {
    setEditing(p);
    setForm({
      name: p.name,
      short_description: p.short_description ?? '',
      description: p.description ?? '',
      product_type: p.product_type || 'physical',
      category_id: p.category_id ? String(p.category_id) : '',
      price: p.price ?? '',
      compare_at_price: p.compare_at_price ?? '',
      wholesale_price: p.wholesale_price ?? '',
      wholesale_min_qty: p.wholesale_min_qty ? String(p.wholesale_min_qty) : '',
      cost_price: p.cost_price ?? '',
      track_stock: p.track_stock,
      stock_quantity: p.stock_quantity != null ? String(p.stock_quantity) : '',
      low_stock_alert: p.low_stock_alert != null ? String(p.low_stock_alert) : '',
      image_url: p.image_url ?? '',
      ai_selling_points: p.ai_selling_points ?? '',
      search_tags: (p.search_tags || []).join(', '),
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) return toast.error('Nome é obrigatório');
    if (!form.price || Number(form.price) <= 0) return toast.error('Preço é obrigatório');

    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      short_description: form.short_description || null,
      description: form.description || null,
      product_type: form.product_type,
      price: Number(form.price),
      track_stock: form.track_stock,
      image_url: form.image_url || null,
      ai_selling_points: form.ai_selling_points || null,
    };

    if (form.category_id) payload.category_id = Number(form.category_id);
    if (form.compare_at_price) payload.compare_at_price = Number(form.compare_at_price);
    if (form.wholesale_price) payload.wholesale_price = Number(form.wholesale_price);
    if (form.wholesale_min_qty) payload.wholesale_min_qty = Number(form.wholesale_min_qty);
    if (form.cost_price) payload.cost_price = Number(form.cost_price);
    if (form.stock_quantity !== '') payload.stock_quantity = Number(form.stock_quantity);
    if (form.low_stock_alert !== '') payload.low_stock_alert = Number(form.low_stock_alert);
    if (form.search_tags) {
      payload.search_tags = form.search_tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
    }

    setSaving(true);
    try {
      if (editing) {
        await api.patch(`/products/${editing.id}`, payload);
        toast.success('Produto atualizado');
      } else {
        await api.post('/products', payload);
        toast.success('Produto criado');
      }
      setShowModal(false);
      loadAll();
    } catch {
      toast.error('Erro ao salvar produto');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/products/${deleteTarget.id}`);
      toast.success('Produto removido');
      setDeleteTarget(null);
      loadAll();
    } catch {
      toast.error('Erro ao remover produto');
    } finally {
      setDeleting(false);
    }
  };

  const columns: ColumnDef<Product>[] = useMemo(() => [
    {
      id: 'image',
      header: '',
      cell: ({ row }) => {
        const p = row.original;
        return (
          <div className="h-10 w-10 rounded-md overflow-hidden bg-muted flex items-center justify-center flex-shrink-0">
            {p.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" />
            ) : (
              <Package className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'name',
      header: 'Nome',
      cell: ({ row }) => (
        <div>
          <div className="font-medium text-foreground">{row.original.name}</div>
          {row.original.short_description && (
            <div className="text-xs text-muted-foreground line-clamp-1 max-w-[320px]">
              {row.original.short_description}
            </div>
          )}
        </div>
      ),
    },
    {
      accessorKey: 'product_type',
      header: 'Tipo',
      cell: ({ row }) => (
        <Badge
          variant="outline"
          className={
            row.original.product_type === 'digital'
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : 'bg-amber-50 text-amber-700 border-amber-200'
          }
        >
          {row.original.product_type === 'digital' ? 'Digital' : 'Físico'}
        </Badge>
      ),
    },
    {
      accessorKey: 'price',
      header: 'Preço',
      cell: ({ row }) => <span className="font-medium">{formatBRL(row.original.price)}</span>,
    },
    {
      accessorKey: 'stock_quantity',
      header: 'Estoque',
      cell: ({ row }) => {
        const p = row.original;
        if (!p.track_stock) return <span className="text-muted-foreground">—</span>;
        const low = p.low_stock_alert != null && p.stock_quantity <= p.low_stock_alert;
        return (
          <span className={low ? 'text-destructive font-medium' : ''}>
            {p.stock_quantity}
          </span>
        );
      },
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) => (
        <Badge
          variant="outline"
          className={
            row.original.is_active
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-gray-100 text-gray-600 border-gray-200'
          }
        >
          {row.original.is_active ? 'Ativo' : 'Inativo'}
        </Badge>
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
      <div className="max-w-7xl mx-auto pb-10 space-y-6" data-density="medium">
        <PageHeader
          title="Produtos"
          description="Gerencie o catálogo que a IA usa para vender"
          actions={
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Novo Produto
            </Button>
          }
        />

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={Package} label="Total" value={stats?.total ?? 0} />
          <StatCard icon={CheckCircle} label="Ativos" value={stats?.active ?? 0} tone="emerald" />
          <StatCard
            icon={AlertTriangle}
            label="Sem Estoque"
            value={stats?.out_of_stock ?? 0}
            tone={stats && stats.out_of_stock > 0 ? 'red' : undefined}
          />
          <StatCard
            icon={Box}
            label="Valor em Estoque"
            value={formatBRL(stats?.stock_value)}
            tone="blue"
          />
        </div>

        {loading ? (
          <TableSkeleton columns={7} rows={8} />
        ) : products.length === 0 ? (
          <EmptyState
            icon={Package}
            title="Nenhum produto cadastrado"
            description="Cadastre seus produtos para que a IA possa vendê-los no WhatsApp."
            actionLabel="Cadastrar Primeiro Produto"
            onAction={openCreate}
          />
        ) : (
          <DataTable
            columns={columns}
            data={products}
            searchPlaceholder="Buscar por nome..."
            searchKey="name"
          />
        )}
      </div>

      {/* Modal criar/editar */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar produto' : 'Novo produto'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-2">
            {/* Básico */}
            <Section title="Básico">
              <div className="grid grid-cols-1 gap-3">
                <Field label="Nome *">
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Ex: Camiseta Premium"
                  />
                </Field>
                <Field label="Descrição curta">
                  <Input
                    value={form.short_description}
                    onChange={(e) => setForm({ ...form, short_description: e.target.value })}
                    placeholder="Aparece nas listagens"
                  />
                </Field>
                <Field label="Descrição completa">
                  <Textarea
                    rows={3}
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Tipo">
                    <Select
                      value={form.product_type}
                      onValueChange={(v) => setForm({ ...form, product_type: v })}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="physical">Físico</SelectItem>
                        <SelectItem value="digital">Digital</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Categoria">
                    <Select
                      value={form.category_id || '__none__'}
                      onValueChange={(v) =>
                        setForm({ ...form, category_id: v === '__none__' ? '' : v })
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Sem categoria" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">Sem categoria</SelectItem>
                        {categories.map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </div>
            </Section>

            {/* Preços */}
            <Section title="Preços">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Preço *">
                  <Input
                    type="number"
                    step="0.01"
                    value={form.price}
                    onChange={(e) => setForm({ ...form, price: e.target.value })}
                  />
                </Field>
                <Field label="Preço comparativo (riscado)">
                  <Input
                    type="number"
                    step="0.01"
                    value={form.compare_at_price}
                    onChange={(e) => setForm({ ...form, compare_at_price: e.target.value })}
                  />
                </Field>
                <Field label="Preço atacado">
                  <Input
                    type="number"
                    step="0.01"
                    value={form.wholesale_price}
                    onChange={(e) => setForm({ ...form, wholesale_price: e.target.value })}
                  />
                </Field>
                <Field label="Qtd. mínima atacado">
                  <Input
                    type="number"
                    value={form.wholesale_min_qty}
                    onChange={(e) => setForm({ ...form, wholesale_min_qty: e.target.value })}
                  />
                </Field>
                <Field label="Custo (opcional)">
                  <Input
                    type="number"
                    step="0.01"
                    value={form.cost_price}
                    onChange={(e) => setForm({ ...form, cost_price: e.target.value })}
                  />
                </Field>
              </div>
            </Section>

            {/* Estoque */}
            <Section title="Estoque">
              <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div>
                  <div className="text-sm font-medium">Controlar estoque</div>
                  <div className="text-xs text-muted-foreground">
                    A IA não oferece produto quando zera o estoque
                  </div>
                </div>
                <Switch
                  checked={form.track_stock}
                  onCheckedChange={(v) => setForm({ ...form, track_stock: v })}
                />
              </div>
              {form.track_stock && (
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <Field label="Quantidade">
                    <Input
                      type="number"
                      value={form.stock_quantity}
                      onChange={(e) => setForm({ ...form, stock_quantity: e.target.value })}
                    />
                  </Field>
                  <Field label="Alerta de baixo estoque">
                    <Input
                      type="number"
                      value={form.low_stock_alert}
                      onChange={(e) => setForm({ ...form, low_stock_alert: e.target.value })}
                    />
                  </Field>
                </div>
              )}
            </Section>

            {/* Imagem */}
            <Section title="Imagem">
              <Field label="URL da imagem">
                <Input
                  value={form.image_url}
                  onChange={(e) => setForm({ ...form, image_url: e.target.value })}
                  placeholder="https://..."
                />
              </Field>
            </Section>

            {/* IA */}
            <Section title="IA de Vendas">
              <Field label="Argumentos de venda">
                <Textarea
                  rows={3}
                  value={form.ai_selling_points}
                  onChange={(e) => setForm({ ...form, ai_selling_points: e.target.value })}
                  placeholder="Pontos fortes que a IA deve destacar..."
                />
              </Field>
              <Field label="Tags de busca (separadas por vírgula)">
                <Input
                  value={form.search_tags}
                  onChange={(e) => setForm({ ...form, search_tags: e.target.value })}
                  placeholder="camiseta, algodão, branco"
                />
              </Field>
            </Section>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
              {editing ? 'Salvar' : 'Criar produto'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmModal
        open={!!deleteTarget}
        title="Excluir produto"
        message={`Tem certeza que deseja excluir ${deleteTarget?.name ?? 'este produto'}? O produto ficará inativo.`}
        confirmLabel={deleting ? 'Excluindo...' : 'Excluir'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        variant="danger"
      />
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
  tone?: 'emerald' | 'red' | 'blue';
}) {
  const toneCls =
    tone === 'emerald'
      ? 'text-emerald-600 bg-emerald-50'
      : tone === 'red'
      ? 'text-destructive bg-destructive/10'
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}
