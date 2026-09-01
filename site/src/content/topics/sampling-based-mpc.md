---
category: "Sampling-based MPC"
title: "Sampling-based Model Predictive Control"
summary: "Predictive control that searches by rolling out sampled action sequences rather than by differentiating a model, and what the humanoid literature has done with it since MuJoCo MPC made it cheap enough to run in real time."
updated: "2026-09-01"
---

## Definition and scope

This area covers model predictive control whose inner optimisation is a search
over sampled action sequences rather than a gradient step: predictive sampling,
model predictive path integral (MPPI) control, cross-entropy and related
derivative-free schemes, together with the work on making them tractable at the
dimensionality a humanoid presents. What qualifies an entry is that the sampling
scheme is the contribution. A locomotion policy that happens to call an MPPI
solver belongs to the locomotion area; a paper about how to draw, weight or
anneal the samples belongs here.

The area was opened deliberately, and its record is thin: five entries spanning
2022 to 2026. Treat what follows as a description of those five rather than as a
survey of the field, and expect the shape of the area to change as the list grows.

## Why the method suits humanoids badly, and why it is used anyway

The appeal is stated plainly in the entries themselves. Sampling needs no
derivatives, so it tolerates contact discontinuities, non-convex costs and
whatever cost terms an engineer wants to write, and it parallelises across the
GPUs that simulation stacks already require. [Predictive Sampling: Real-time
Behaviour Synthesis with MuJoCo](/awesome-humanoid-robot-learning/papers/predictive-sampling-real-time-behaviour-synthesis-with-mujoco)
is the reference point for that argument in this list.

The difficulty is equally plain, and it is what the later entries are about.
[Hybrid Feedback Sampling for Sample-Efficient Model Predictive
Control](/awesome-humanoid-robot-learning/papers/hybrid-feedback-sampling-for-sample-efficient-model-predictive-control)
states the problem directly: for high-dimensional and open-loop unstable systems
— which is a fair description of a humanoid — the number of samples needed to
improve the control sequence grows exponentially with the horizon. A humanoid is
close to the worst case for a method that searches blindly.

The three intervening entries each attack that cost from a different side.
[Full-Order Sampling-Based MPC for Torque-Level Locomotion Control via
Diffusion-Style Annealing](/awesome-humanoid-robot-learning/papers/full-order-sampling-based-mpc-for-torque-level-locomotion-control-via-diffusion-)
takes an annealing schedule to the sampling distribution rather than reducing the
model. [Reference-Free Sampling-Based Model Predictive
Control](/awesome-humanoid-robot-learning/papers/reference-free-sampling-based-model-predictive-control)
removes the handcrafted gait pattern and contact sequence the search would
otherwise be organised around, and reports trotting, galloping, jumping and
handstand balancing emerging from the search itself.
[Projection-Retraction MPPI: Exact Constraint-Manifold Control for
Manipulators](/awesome-humanoid-robot-learning/papers/projection-retraction-mppi-exact-constraint-manifold-control-for-manipulators)
addresses a different weakness — that a sampler has no native way to respect a
constraint that must hold throughout a motion, such as a closed kinematic chain
between two grasping arms — by projecting samples onto the constraint manifold.

## What this area does not yet answer

Nothing in these five entries settles how sampling-based MPC should relate to the
learned policies that dominate the rest of this list. Both appear as controllers
for the same tasks, both are evaluated on locomotion and manipulation, and the
entries here do not compare against a reinforcement-learning baseline on equal
terms. Whether the two are alternatives, or whether sampling is best used to
generate data and reference behaviour for a policy that is then distilled, is not
answered by anything recorded here.
