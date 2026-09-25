import pytest
import numpy as np
import networkx as nx
from powergrid_synth.transmission.generation_dispatcher import GenerationDispatcher

@pytest.fixture
def sample_grid():
    G = nx.Graph()
    # 10 Generators, 100 MW each = 1000 MW total
    for i in range(10):
        G.add_node(i, bus_type='Gen', pg_max=100.0)
    
    # Loads
    G.add_node(10, bus_type='Load', pl=200.0)
    G.add_node(11, bus_type='Load', pl=200.0)
    # Total Load = 400 MW (40% Loading)
    return G

class TestGenerationDispatcher:

    def test_initialization(self, sample_grid):
        dispatcher = GenerationDispatcher(sample_grid, ref_sys_id=1)
        assert dispatcher.mu_committed is not None

    def test_select_uncommitted(self, sample_grid):
        dispatcher = GenerationDispatcher(sample_grid)
        norm_pg = np.array([[i, 1.0] for i in range(10)])
        
        uncomm, remaining = dispatcher._select_uncommitted(norm_pg)
        assert 1 <= len(uncomm) <= 2
        assert uncomm.shape[1] == 3
        assert np.all(uncomm[:, 2] == 0.0)

    def test_select_committed(self, sample_grid):
        dispatcher = GenerationDispatcher(sample_grid)
        norm_pg = np.array([[i, 1.0] for i in range(8)])
        
        # Pass total units count (10) explicitly
        comm, remaining = dispatcher._select_committed(norm_pg, 10)
        # 40-50% of 10 is 4-5. 
        # But random factors apply. Just check bounds.
        assert 3 <= len(comm) <= 6

    def test_dispatch_balancing_light(self, sample_grid):
        """Test dispatch with 400 MW load (Excess scenario initial)."""
        dispatcher = GenerationDispatcher(sample_grid)
        result = dispatcher.dispatch()
        
        total_gen = sum(result.values())
        total_load = 400.0
        
        print(f"Target: {total_load}, Actual: {total_gen}")
        assert abs(total_gen - total_load) < 0.1 * total_load

    def test_dispatch_balancing_heavy(self, sample_grid):
        """Test dispatch with 800 MW load (Deficit scenario initial)."""
        sample_grid.nodes[10]['pl'] = 400.0
        sample_grid.nodes[11]['pl'] = 400.0 
        
        dispatcher = GenerationDispatcher(sample_grid)
        result = dispatcher.dispatch()
        
        total_gen = sum(result.values())
        total_load = 800.0
        
        print(f"Target: {total_load}, Actual: {total_gen}")
        assert abs(total_gen - total_load) < 0.1 * total_load

    def test_dispatch_no_generators(self):
        """dispatch returns empty dict when grid has no Gen nodes."""
        grid = nx.Graph()
        for i in range(5):
            grid.add_node(i, bus_type='Load', pl=10.0)
        dispatcher = GenerationDispatcher(grid, ref_sys_id=1)
        result = dispatcher.dispatch()
        assert result == {}

    def test_select_uncommitted_empty(self, sample_grid):
        """_select_uncommitted returns empty arrays for empty input."""
        dispatcher = GenerationDispatcher(sample_grid, ref_sys_id=1)
        empty = np.array([]).reshape(0, 2)
        uncomm, remaining = dispatcher._select_uncommitted(empty)
        assert len(uncomm) == 0
        assert len(remaining) == 0

    def test_generate_alphas_alpha_mod_nonzero(self, sample_grid):
        """_generate_alphas with alpha_mod != 0 produces 99.5% positive, 0.5% negative."""
        dispatcher = GenerationDispatcher(sample_grid, ref_sys_id=1)
        dispatcher.alpha_mod = 1
        np.random.seed(42)
        n_comm = 200
        alphas = dispatcher._generate_alphas(n_comm)
        assert len(alphas) == n_comm
        assert np.any(alphas < 0)

    def test_generate_alphas_zero_count(self, sample_grid):
        """_generate_alphas with n_comm=0 returns empty array."""
        dispatcher = GenerationDispatcher(sample_grid, ref_sys_id=1)
        alphas = dispatcher._generate_alphas(0)
        assert len(alphas) == 0

    def test_generate_alphas_alpha_mod_nonzero_small(self, sample_grid):
        """_generate_alphas with alpha_mod != 0 and small n_comm hits n_005=0 path."""
        dispatcher = GenerationDispatcher(sample_grid, ref_sys_id=1)
        dispatcher.alpha_mod = 1
        # n_comm=1: n_995=round(1*0.995)=1, n_005=0 → returns a1 directly (line 198)
        alphas = dispatcher._generate_alphas(1)
        assert len(alphas) == 1
        assert alphas[0, 0] >= 0  # no negative dispatch for such a small set

    def test_dispatch_balances_exactly(self, sample_grid):
        """Generation matches load to numerical precision, not just within 1%."""
        np.random.seed(0)
        result = GenerationDispatcher(sample_grid).dispatch()
        assert sum(result.values()) == pytest.approx(400.0, rel=1e-6)
        assert all(0.0 <= p <= 100.0 + 1e-9 for p in result.values())

    def test_dispatch_balances_skewed_large_grid(self):
        """Heavy-tailed capacities on a large grid (thousands of buses) still balance.

        The uncommitted selection picks units near Uniform[0, 0.6] of the
        largest unit, which here are the few large units holding much of the
        capacity; balancing must switch them back on to meet the load.
        """
        rng = np.random.default_rng(1)
        caps = np.concatenate([rng.lognormal(3.5, 1.0, 1900), rng.uniform(1000, 4800, 100)])
        grid = nx.Graph()
        for i, cap in enumerate(caps):
            grid.add_node(i, bus_type='Gen', pg_max=float(cap))
        total_load = 0.8 * caps.sum()
        grid.add_node(len(caps), bus_type='Load', pl=float(total_load))

        np.random.seed(0)
        result = GenerationDispatcher(grid).dispatch()
        assert sum(result.values()) == pytest.approx(total_load, rel=1e-6)
        for bus, p in result.items():
            assert p <= grid.nodes[bus]['pg_max'] + 1e-9

    def test_dispatch_infeasible_load_warns(self, sample_grid, capsys):
        """Load above total capacity: all units at full output and a warning."""
        sample_grid.nodes[10]['pl'] = 1000.0
        sample_grid.nodes[11]['pl'] = 1000.0
        result = GenerationDispatcher(sample_grid).dispatch()
        assert sum(result.values()) == pytest.approx(1000.0)
        assert "falls short of total load" in capsys.readouterr().out

    def test_dispatch_zero_load(self, sample_grid):
        """No load: every unit is switched off."""
        sample_grid.nodes[10]['pl'] = 0.0
        sample_grid.nodes[11]['pl'] = 0.0
        result = GenerationDispatcher(sample_grid).dispatch()
        assert sum(result.values()) == pytest.approx(0.0, abs=1e-9)

    def test_scale_committed_alphas_keeps_negative(self):
        """Negative dispatch factors are kept; positive ones are scaled to the target."""
        comm_units = np.array([[0, 1.0, 0.2], [1, 1.0, 0.4], [2, 0.5, -0.5]])
        GenerationDispatcher._scale_committed_alphas(comm_units, 0.95)
        assert comm_units[2, 2] == -0.5
        assert np.sum(comm_units[:, 1] * comm_units[:, 2]) == pytest.approx(0.95)
        assert np.all(comm_units[:2, 2] <= 1.0)

    def test_invalid_ref_sys_fallback(self):
        """Invalid ref_sys_id falls back to ref_sys_id=1 without error."""
        grid = nx.Graph()
        grid.add_node(0, bus_type='Load', pl=10.0)
        dispatcher = GenerationDispatcher(grid, ref_sys_id=99)
        assert dispatcher.stats is not None