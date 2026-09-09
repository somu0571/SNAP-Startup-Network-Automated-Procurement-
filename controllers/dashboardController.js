const Challenge = require('../models/Challenge');
const Application = require('../models/Application');
const Pilot = require('../models/Pilot');
const Startup = require('../models/Startup');
const User = require('../models/User');
const matchingService = require('../services/matchingService');

// Landing Page Controller Handler
exports.getLandingPage = async (req, res) => {
  try {
    // Run database count queries in parallel
    const [usersCount, challengesCount, pilotsCount, totalBudgetResult] = await Promise.all([
      User.countDocuments(),
      Challenge.countDocuments({ status: 'PUBLISHED' }),
      Pilot.countDocuments({ status: 'ACTIVE' }),
      Pilot.aggregate([
        { $match: { status: { $in: ['ACTIVE', 'SCALE_UP_RECOMMENDED', 'COMPLETED'] } } },
        { $group: { _id: null, total: { $sum: '$budget' } } }
      ])
    ]);

    // Format total budget into a readable currency string
    const rawBudget = totalBudgetResult[0]?.total || 0;
    const procuredValue = rawBudget >= 1000000
      ? `$${(rawBudget / 1000000).toFixed(1)}M`
      : `$${rawBudget.toLocaleString()}`;

    const metrics = {
      usersCount,
      challengesCount,
      pilotsCount,
      procuredValue
    };

    res.render('index', {
      user: req.session ? req.session.user : null,
      metrics
    });
  } catch (err) {
    console.error('Error loading landing page metrics:', err);

    // Graceful fallback with zeroed metrics in case of query error
    res.render('index', {
      user: req.session ? req.session.user : null,
      metrics: {
        usersCount: 0,
        challengesCount: 0,
        pilotsCount: 0,
        procuredValue: '$0'
      }
    });
  }
};

exports.getGovernmentDashboard = async (req, res) => {
  try {
    const deptId = req.session.user.department;

    // Stats
    const totalChallenges = await Challenge.countDocuments({ department: deptId });
    const publishedChallenges = await Challenge.countDocuments({ department: deptId, status: 'PUBLISHED' });

    const deptChallenges = await Challenge.find({ department: deptId }).select('_id');
    const challengeIds = deptChallenges.map(c => c._id);

    const totalApplications = await Application.countDocuments({ challenge: { $in: challengeIds } });
    const activePilots = await Pilot.countDocuments({ department: deptId, status: 'ACTIVE' });
    const successfulPilots = await Pilot.countDocuments({ department: deptId, status: 'SCALE_UP_RECOMMENDED' });

    // Recent Data
    const recentChallenges = await Challenge.find({ department: deptId }).sort({ createdAt: -1 }).limit(5);
    const recentPilots = await Pilot.find({ department: deptId }).populate('startup challenge').sort({ startDate: -1 }).limit(5);

    res.render('layouts/main', {
      body: 'government/dashboard',
      stats: { totalChallenges, publishedChallenges, totalApplications, activePilots, successfulPilots },
      recentChallenges,
      recentPilots
    });
  } catch (err) {
    console.error(err);
    res.redirect('/');
  }
};

exports.getStartupDashboard = async (req, res) => {
  try {
    const startupId = req.session.user.startup;
    const startup = await Startup.findById(startupId);

    let recommendedChallenges = [];
    if (startup) {
      recommendedChallenges = await matchingService.getRecommendedChallenges(startup);
      // Limit to top 3
      recommendedChallenges = recommendedChallenges.slice(0, 3);
    }

    const applications = await Application.find({ startup: startupId }).populate('challenge').sort({ submittedAt: -1 }).limit(5);
    const activePilots = await Pilot.find({ startup: startupId, status: 'ACTIVE' }).populate('challenge department').sort({ startDate: -1 });

    const isProfileComplete = startup && startup.description && startup.technologies.length > 0;

    res.render('layouts/main', {
      body: 'startup/dashboard',
      startup,
      isProfileComplete,
      recommendedChallenges,
      applications,
      activePilots
    });
  } catch (err) {
    console.error(err);
    res.redirect('/');
  }
};

exports.getAdminDashboard = async (req, res) => {
  try {
    const Department = require('../models/Department');

    const totalDepartments = await Department.countDocuments();
    const totalStartups = await Startup.countDocuments();
    const totalChallenges = await Challenge.countDocuments();
    const totalApplications = await Application.countDocuments();
    const totalPilots = await Pilot.countDocuments();
    const totalUsers = await User.countDocuments();

    const recentChallenges = await Challenge.find().populate('department').sort({ createdAt: -1 }).limit(5);
    const recentPilots = await Pilot.find().populate('startup challenge department').sort({ startDate: -1 }).limit(5);
    const recentStartups = await Startup.find().sort({ createdAt: -1 }).limit(5);

    res.render('layouts/main', {
      body: 'admin/dashboard',
      stats: {
        totalDepartments,
        totalStartups,
        totalChallenges,
        totalApplications,
        totalPilots,
        totalUsers
      },
      recentChallenges,
      recentPilots,
      recentStartups
    });
  } catch (err) {
    console.error(err);
    res.redirect('/');
  }
};

exports.getSeedPage = async (req, res) => {
  res.render('layouts/main', { body: 'admin/seed' });
};

exports.postSeedData = async (req, res) => {
  try {
    const seed = require('../seed/seed');
    await seed();
    req.session.success = 'Database re-seeded successfully with rich demo data!';
    res.redirect('/admin/dashboard');
  } catch (err) {
    console.error('Seed execution failed:', err);
    req.session.error = 'Failed to re-seed database: ' + err.message;
    res.redirect('/admin/dashboard');
  }
};
