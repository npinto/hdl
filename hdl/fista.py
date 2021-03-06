import theano
from theano import tensor as T
from theano import function, Param, shared, In, Out, sandbox
import numpy as np

class Fista(object):

    def __init__(self,problem_type='l2l1',**kargs):
        self.L = T.scalar('L',dtype=theano.config.floatX)
        self.tk_factor = T.scalar('tk_factor',dtype=theano.config.floatX)
        self.fy = T.scalar('fy',dtype=theano.config.floatX)

        xinit = kargs.get('xinit')
        self.xk = shared(xinit)
        self.xkm = shared(np.zeros_like(xinit,dtype=theano.config.floatX))
        self.y = shared(np.zeros_like(xinit,dtype=theano.config.floatX))
        self.gfy = shared(np.zeros_like(xinit,dtype=theano.config.floatX))

        if problem_type == 'l2l1':
            self._setup_l2l1(**kargs)
        elif problem_type == 'l2subspacel1slow':
            self._setup_l2subspacel1slow(**kargs)
        elif problem_type == 'l2subspacel1':
            self._setup_l2subspacel1(**kargs)
        elif problem_type == 'l2Ksubspacel1':
            self._setup_l2Ksubspacel1(**kargs)
        elif problem_type == 'l2elastic':
            self._setup_l2elastic(**kargs)
        else:
            assert NotImplementedError, '%s problem_type unknown'%problem_type

        self._setup_fista()

    def _setup_l2subspacel1slow(self, **kargs):
        # Setup variables
        self.x = kargs['x']
        self.A = kargs['A']
        self.lam_sparse = kargs['lam_sparse']
        self.lam_slow = kargs['lam_slow']

        # eval and gradient at current point
        from theano_methods import T_l2_cost, T_gl2_cost, T_subspacel1_slow_cost, T_subspacel1_slow_shrinkage
        self.T_f_cost = lambda point: T_l2_cost(self.x,point,self.A)
        self.T_f_grad = lambda point: T_gl2_cost(self.x,point,self.A)
        self.T_g_cost = lambda point: T_subspacel1_slow_cost(point,lam_sparse=self.lam_sparse,lam_slow=self.lam_slow)
        self.T_point_shrinkage = lambda point: T_subspacel1_slow_shrinkage(point,self.L,lam_sparse=self.lam_sparse,lam_slow=self.lam_slow)

    def _setup_l2subspacel1(self, **kargs):
        # Setup variables
        self.x = kargs['x']
        self.A = kargs['A']
        self.lam_sparse = kargs['lam_sparse']

        # eval and gradient at current point
        from theano_methods import T_l2_cost, T_gl2_cost, T_subspacel1_cost, T_subspacel1_shrinkage
        self.T_f_cost = lambda point: T_l2_cost(self.x,point,self.A)
        self.T_f_grad = lambda point: T_gl2_cost(self.x,point,self.A)
        self.T_g_cost = lambda point: T_subspacel1_cost(point,lam_sparse=self.lam_sparse)
        self.T_point_shrinkage = lambda point: T_subspacel1_shrinkage(point,self.L,lam_sparse=self.lam_sparse)

    def _setup_l2Ksubspacel1(self, **kargs):
        # Setup variables
        self.x = kargs['x']
        self.A = kargs['A']
        self.lam_sparse = kargs['lam_sparse']
        self.K = kargs['K']

        # eval and gradient at current point
        from theano_methods import T_l2_cost, T_gl2_cost, T_Ksubspacel1_cost, T_Ksubspacel1_shrinkage
        self.T_f_cost = lambda point: T_l2_cost(self.x,point,self.A)
        self.T_f_grad = lambda point: T_gl2_cost(self.x,point,self.A)
        self.T_g_cost = lambda point: T_Ksubspacel1_cost(point,lam_sparse=self.lam_sparse,K=self.K)
        self.T_point_shrinkage = lambda point: T_Ksubspacel1_shrinkage(point,self.L,lam_sparse=self.lam_sparse,K=self.K)

    def _setup_l2elastic(self,**kargs):

        # Setup variables
        self.x = kargs['x']
        self.A = kargs['A']
        self.lam_sparse = kargs['lam_sparse']
        self.lam_l2 = kargs['lam_l2']

        # eval and gradient at current point
        from theano_methods import T_l2_cost, T_gl2_cost, T_elastic_cost, T_elastic_shrinkage
        self.T_f_cost = lambda point: T_l2_cost(self.x,point,self.A)
        self.T_f_grad = lambda point: T_gl2_cost(self.x,point,self.A)
        self.T_g_cost = lambda point: T_elastic_cost(point,self.lam_sparse,self.lam_l2)
        self.T_point_shrinkage = lambda point: T_elastic_shrinkage(point,self.L,self.lam_sparse,self.lam_l2)

    def _setup_l2l1(self,**kargs):

        # Setup variables
        self.x = kargs['x']
        self.A = kargs['A']
        self.lam = kargs['lam']

        # eval and gradient at current point
        from theano_methods import T_l2_cost, T_gl2_cost, T_l1_cost, T_a_shrinkage
        self.T_f_cost = lambda point: T_l2_cost(self.x,point,self.A)
        self.T_f_grad = lambda point: T_gl2_cost(self.x,point,self.A)
        self.T_g_cost = lambda point: T_l1_cost(point,self.lam)
        self.T_point_shrinkage = lambda point: T_a_shrinkage(point,self.L,self.lam)

    def _setup_fista(self):
        # eval and gradient at current point
        #self.fgradf = function([],T_l2_cost(self.x,self.y,self.A),updates=[(self.gfy,T_gl2_cost(self.x,self.y,self.A))])
        self.fgradf = function([],self.T_f_cost(self.y),updates=[(self.gfy,self.T_f_grad(self.y))])

        # auxiliary problem
        ply = self.y - (1./self.L)*self.gfy
        ply0 = self.T_point_shrinkage(ply)
        fply = self.T_f_cost(ply0)
        ply1 = ply0 - self.y
        Q2 = T.sum(self.gfy*ply1)
        Q3 = self.L/2 * T.sum(ply1**2)
        Q = self.fy + Q2 + Q3
        self.fista_auxiliary = function([self.fy,self.L],[fply, Q],updates=[(self.xk,ply0)])

        gply = self.T_g_cost(self.xk)
        self.g = function([],gply)

        self.xk2xkm = function([],[],updates=[(self.xk,self.xkm)])
        self.f = function([],self.T_f_cost(self.xk))

        # fista update
        y_update = self.xk + self.tk_factor * (self.xkm - self.xk)
        self.fista_update = function([self.tk_factor], [],updates=[(self.y,y_update)],allow_input_downcast=True)
        self.xkm2xk = function([],[],updates=[(self.xkm,self.xk)])

    def _reset(self,xinit,x):
        """reset the memory variables for next fista run
        """

        self.x.set_value(x)
        self.xk.set_value(xinit)
        self.xkm.set_value(np.zeros_like(xinit))
        self.y.set_value(np.zeros_like(xinit))

    def _reset_A(self,A):
        """set the parameter matrix for the problem (fixed for estimation)
        """

        self.A.set_value(A)

    def __call__(self, xinit, x, L=.1,Lstep=1.5,maxiter=50,maxline=20,errthres=1e-4,verbose=False):

        """
        fista algorithm using Theano
        """

        self._reset(xinit,x)

        history = []
        niter = 0
        converged = False
        tk = 1.

        if verbose:
            print 'niter, linesearchdone, nline, L, fy, Q2, Q3, Q, fply'

        while not converged and niter < maxiter:
            fy = self.fgradf()

            fply = 0.
            gply = 0.
            Q = 0.
            nline = 0
            linesearchdone = False

            while not linesearchdone:
                fply, Q = self.fista_auxiliary(fy,L)

                # check if F(beta) < Q(pl(y), \t)
                if fply <= Q: # and Fply + Gply <= F then
                    # now evaluate G here
                    gply  = self.g()
                    linesearchdone = True
                elif nline >= maxline:
                    linesearchdone = True
                    self.xk2xkm()
                    fply  = self.f()
                    gply= self.g()
                else:
                    L = L * Lstep

                nline += 1
                if verbose:
                    print '%i, %s, %i, %2.2e, %2.8e,%2.2e,%2.2e,%2.2e,%2.2e'%(niter, linesearchdone, nline, L, fy, 0, 0, Q, fply)


            # bookkeeping
            fval = fply + gply
            history.append({})
            history[niter]['nline'] = nline
            history[niter]['L'] = L
            history[niter]['F'] = fval
            history[niter]['Fply'] = fply
            history[niter]['Gply'] = gply
            history[niter]['Q'] = Q

            if verbose:
                history[niter]['xk'] = None#xk.copy()
                history[niter]['y'] = None#y.copy()

            # are we done?
            if niter > 0 and np.abs(history[niter]['F'] - history[niter-1]['F']) <= errthres:
                return self.xk.get_value(), history

            if niter+1 >= maxiter:
                return self.xk.get_value(), history

            #if doFistaUpdate:
            # do the FISTA step
            tkp = (1 + np.sqrt(1 + 4*tk*tk)) / 2
            tk_factor = ((1-tk)/tkp)
            self.fista_update(tk_factor)
            # store for next iterations
            # x(k-1) = x(k)
            #xkm[:] = xk
            self.xkm2xk()

            # t(k) = t(k+1)
            tk = tkp

            niter += 1

        raise AssertionError, 'fista.__call__() did not return'

