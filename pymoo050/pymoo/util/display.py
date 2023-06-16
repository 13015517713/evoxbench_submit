import numpy as np

from pymoo.indicators.gd import GD
from pymoo.indicators.igd import IGD
from pymoo.indicators.hv import Hypervolume
from pymoo.util.termination.f_tol import MultiObjectiveSpaceToleranceTermination


def pareto_front_if_possible(problem):
    try:
        return problem.pareto_front()
    except:
        return None


class Output:

    def __init__(self, default_width=12) -> None:
        super().__init__()
        self.default_width = default_width
        self.attrs = []

    def append(self, name, number, format_if_float=True, width=None):
        if width is None:
            width = self.default_width
        if format_if_float and isinstance(number, float):
            number = self.format_float(number, width)

        self.attrs.append([name, number, width])

    def format_float(self, number, width):
        if number >= 10 or number * 1e5 < 1:
            return f"%.{width - 7}E" % number
        else:
            return f"%.{width - 3}f" % number

    def extend(self, *args):
        for arg in args:
            self.append(*arg)

    def clear(self):
        self.attrs = []

    def create_regex(self):
        return " | ".join(["{}"] * len(self.attrs))

    def do(self):
        if len(self.attrs) > 0:
            regex = self.create_regex()
            val = regex.format(*[str(val).rjust(width) for _, val, width in self.attrs])
            print(val)

    def header(self):
        regex = self.create_regex()
        s = regex.format(*[str(name).center(width) for name, _, width in self.attrs])
        print("=" * len(s))
        print(s)
        print("=" * len(s))


class Display:

    def __init__(self, output=None, attributes=None):
        super().__init__()
        self.output = output
        if self.output is None:
            self.output = Output()

        self.display_header = True
        self.pareto_front_is_available = None
        self.pf = None
        self.attributes = attributes

    def do(self, problem, evaluator, algorithm, pf=None, show=True):

        try:

            # if this runs for the first time - executed only once!
            if self.pareto_front_is_available is None:

                if isinstance(pf, bool) and not pf:
                    self.pf, self.pareto_front_is_available = None, False

                # try to get the pareto front from the problem
                elif pf is None or (isinstance(pf, bool) and pf):
                    self.pf = pareto_front_if_possible(problem)
                    self.pareto_front_is_available = self.pf is not None

                # the pf should be given directly
                else:
                    self.pf = pf
                    self.pf, self.pareto_front_is_available = pf, True

            self.output.clear()

            # get the actual attributes to display
            self._do(problem, evaluator, algorithm)

            if self.attributes is not None:
                self.output.attrs = [attr for attr in self.output.attrs if attr[0] in self.attributes]

            if show:
                if self.display_header:
                    self.output.header()
                # print the actually line
                self.output.do()

        # catch any exception to make sure the algorithm does not fail because of printing
        except Exception as ex:
            print("WARNING: Error while preparing the output to be printed.")

        self.display_header = False

    def _do(self, problem, evaluator, algorithm):
        self.output.extend(*[('n_gen', algorithm.n_gen, False, 5), ('n_eval', evaluator.n_eval, False, 7)])


class SingleObjectiveDisplay(Display):

    def __init__(self, favg=True, **kwargs):
        super().__init__(**kwargs)
        self.favg = favg

    def _do(self, problem, evaluator, algorithm):
        super()._do(problem, evaluator, algorithm)

        opt = algorithm.opt[0]
        F, CV, feasible = algorithm.pop.get("F", "CV", "feasible")
        feasible = np.where(feasible[:, 0])[0]

        if problem.n_constr > 0:
            self.output.append("cv (min)", opt.CV[0])
            self.output.append("cv (avg)", np.mean(CV))

        if opt.feasible[0]:

            self.output.append("fopt", opt.F[0])
            if self.pareto_front_is_available:
                self.output.append("fopt_gap", opt.F[0] - self.pf.flatten()[0])
            if self.favg:
                if len(feasible) > 0:
                    self.output.append("favg", np.mean(F[feasible]))
                else:
                    self.output.append("favg", "-")
        else:
            self.output.append("fopt", "-")
            if self.pareto_front_is_available:
                self.output.append("fopt_gap", "-")
            if self.favg:
                self.output.append("favg", "-")


class MultiObjectiveDisplay(Display):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.term = MultiObjectiveSpaceToleranceTermination()

    def _do(self, problem, evaluator, algorithm):
        super()._do(problem, evaluator, algorithm)

        F, CV, feasible = algorithm.pop.get("F", "CV", "feasible")
        feasible = np.where(feasible[:, 0])[0]

        if problem.n_constr > 0:
            self.output.append("cv (min)", CV.min())
            self.output.append("cv (avg)", np.mean(CV))

        if self.pareto_front_is_available:
            igd, gd, hv = "-", "-", "-"
            if len(feasible) > 0:
                _F = algorithm.opt.get("F")
                igd, gd = IGD(self.pf, zero_to_one=True).do(_F), GD(self.pf, zero_to_one=True).do(_F)
                if problem.n_obj == 2:
                    hv = Hypervolume(pf=self.pf, zero_to_one=True).do(_F)

            self.output.extend(*[('igd', igd), ('gd', gd)])
            if problem.n_obj == 2:
                self.output.append("hv", hv)

        else:
            self.output.append("n_nds", len(algorithm.opt), width=7)
            self.term.do_continue(algorithm)

            max_from, eps = "-", "-"

            if len(self.term.metrics) > 0:
                metric = self.term.metrics[-1]
                tol = self.term.tol
                delta_ideal, delta_nadir, delta_f = metric["delta_ideal"], metric["delta_nadir"], metric["delta_f"]

                if delta_ideal > tol:
                    max_from = "ideal"
                    eps = delta_ideal
                elif delta_nadir > tol:
                    max_from = "nadir"
                    eps = delta_nadir
                else:
                    max_from = "f"
                    eps = delta_f

            self.output.append("eps", eps)
            self.output.append("indicator", max_from)
