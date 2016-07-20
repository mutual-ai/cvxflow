"""Tests for SCS tensorflow."""

import cvxpy as cvx
import numpy as np
import tensorflow as tf

from cvxflow import scs_tf

def form_lp(m, n):
    """Form LP with CVXPY."""
    np.random.seed(0)
    A = np.abs(np.random.randn(m,n))
    b = A.dot(np.abs(np.random.randn(n)))
    c = np.random.rand(n) + 0.5
    x = cvx.Variable(n)
    return cvx.Problem(cvx.Minimize(c.T*x), [A*x == b, x >= 0])

def expected_subspace_projection(A0, b0, c0, rhs):
    from scipy import linalg
    m, n = A0.shape

    Q = np.zeros((m+n+1, m+n+1))
    Q[0:n, n:n+m]       = A0.T
    Q[0:n, n+m:n+m+1]   = c0
    Q[n:n+m, 0:n]       = -A0
    Q[n:n+m, n+m:n+m+1] = b0
    Q[n+m:n+m+1, 0:n]   = -c0.T
    Q[n+m:n+m+1, n:n+m] = -b0.T

    return linalg.solve(np.eye(m+n+1) + Q, rhs)

def expected_cone_projection(x, n, dims):
    idx = slice(n+dims["f"], n+dims["f"]+dims["l"])
    x[idx] = np.maximum(x[idx], 0)
    x[-1] = np.maximum(x[-1], 0)
    return x

def test_scs():
    prob = form_lp(5,10)
    data = prob.get_problem_data(cvx.SCS)
    m, n = data["A"].shape

    # input data
    A = tf.placeholder(tf.float32, shape=(m, n))
    b = tf.placeholder(tf.float32, shape=(m, 1))
    c = tf.placeholder(tf.float32, shape=(n, 1))

    # variables
    u = scs_tf.PrimalVars(
        tf.Variable(tf.expand_dims(tf.zeros(n), 1)),
        tf.Variable(tf.expand_dims(tf.zeros(m), 1)),
        tf.Variable(tf.expand_dims(tf.ones(1), 1)))
    u_tilde = scs_tf.PrimalVars(
        tf.Variable(tf.expand_dims(tf.zeros(n), 1)),
        tf.Variable(tf.expand_dims(tf.zeros(m), 1)),
        tf.Variable(tf.expand_dims(tf.ones(1), 1)))
    v = scs_tf.DualVars(
        tf.Variable(tf.expand_dims(tf.zeros(n), 1)),
        tf.Variable(tf.expand_dims(tf.zeros(m), 1)),
        tf.Variable(tf.expand_dims(tf.ones(1), 1)))

    # random data
    np.random.seed(0)
    A0 = np.random.randn(m,n)
    b0 = np.random.randn(m,1)
    c0 = np.random.randn(n,1)
    feed_dict = {A: A0, b: b0, c: c0}

    u0 = np.zeros(m+n+1)
    v0 = np.zeros(m+n+1)
    u0[-1] = 1
    v0[-1] = 1

    # operations
    init = tf.initialize_all_variables()
    subspace_projection_op = scs_tf.subspace_projection(A, b, c, u, u_tilde, v)
    cone_projection_op = scs_tf.cone_projection(data["dims"], u, u_tilde, v)
    dual_update_op = scs_tf.dual_update(u, u_tilde, v)

    with tf.Session() as sess:
        sess.run(init)

        print "first iteration"
        u_tilde0 = expected_subspace_projection(A0, b0, c0, u0 + v0)
        sess.run(subspace_projection_op, feed_dict=feed_dict)
        np.testing.assert_allclose(u_tilde0[:n],    sess.run(u_tilde.x)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u_tilde0[n:n+m], sess.run(u_tilde.y)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u_tilde0[-1],    sess.run(u_tilde.tau),     rtol=1e-4, atol=1e-4)

        u0 = expected_cone_projection(u_tilde0 - v0, n, data["dims"])
        sess.run(cone_projection_op)
        np.testing.assert_allclose(u0[:n],    sess.run(u.x)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u0[n:n+m], sess.run(u.y)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u0[-1],    sess.run(u.tau),     rtol=1e-4, atol=1e-4)

        v0 = v0 - u_tilde0 + u0
        sess.run(dual_update_op)
        np.testing.assert_allclose(v0[:n],    sess.run(v.r)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(v0[n:n+m], sess.run(v.s)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(v0[-1],    sess.run(v.kappa),   rtol=1e-4, atol=1e-4)

        print "second iteration"
        u_tilde0 = expected_subspace_projection(A0, b0, c0, u0 + v0)
        sess.run(subspace_projection_op, feed_dict=feed_dict)
        np.testing.assert_allclose(u_tilde0[:n],    sess.run(u_tilde.x)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u_tilde0[n:n+m], sess.run(u_tilde.y)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u_tilde0[-1],    sess.run(u_tilde.tau),     rtol=1e-4, atol=1e-4)

        u0 = expected_cone_projection(u_tilde0 - v0, n, data["dims"])
        sess.run(cone_projection_op)
        np.testing.assert_allclose(u0[:n],    sess.run(u.x)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u0[n:n+m], sess.run(u.y)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(u0[-1],    sess.run(u.tau),     rtol=1e-4, atol=1e-4)

        v0 = v0 - u_tilde0 + u0
        sess.run(dual_update_op)
        np.testing.assert_allclose(v0[:n],    sess.run(v.r)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(v0[n:n+m], sess.run(v.s)[:,0],  rtol=1e-4, atol=1e-4)
        np.testing.assert_allclose(v0[-1],    sess.run(v.kappa),   rtol=1e-4, atol=1e-4)
