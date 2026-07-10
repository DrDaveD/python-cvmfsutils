# OBS expects the name %%release_prefix; do not change the name
%define release_prefix 1

Summary: Inspect CernVM-FS repositories
Name: python-cvmfsutils
Version: 0.6.0
Release: %{release_prefix}%{?dist}
Source0: %{name}-0.6.0.tar.gz
License: (c) 2015 CERN - BSD License
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-0.6.0-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Rene Meusel <rene.meusel@cern.ch>
Url: http://cernvm.cern.ch

%if 0%{?rhel} == 8
%define PYV python38
%else
%define PYV python3
%endif
BuildRequires: %{PYV}
BuildRequires: %{PYV}-rpm-macros
BuildRequires: %{PYV}-pip
BuildRequires: %{PYV}-setuptools

Requires: %{PYV}-dateutil
Requires: %{PYV}-requests
Requires: %{PYV}-cryptography

%description
The CernVM-FS python package allows for the inspection of CernVM-FS
repositories using python. In particular to browse their file catalog
hierarchy, inspect CernVM-FS repository manifests (a.k.a. .cvmfspublished
files) and the history of named snapshots inside any CernVM-FS repository.

%prep
#%%setup -n %{name}-0.6.0 -n %{name}-0.6.0
%autosetup -n %{name}-0.6.0

%build
# No build step needed - pip install handles everything

%install
%if 0%{?rhel} == 9
export SETUPTOOLS_SCM_PRETEND_VERSION=0.6.0
%endif
python3 -m pip install --no-deps -v --root=%{buildroot} %{_sourcedir}/%{name}-0.6.0.tar.gz

%clean
rm -rf $RPM_BUILD_ROOT

%files
%license COPYING
%doc README.md
%{_bindir}/*
%{python3_sitelib}/*

%changelog
# - Replace M2Crypto dependency with cryptography library

* Wed Aug 13 2025 Chris Burr <christopher.burr@cern.ch> - 0.6.0-1
- Modernize build system to use pyproject.toml with setuptools
- Use setuptools-scm for version management
- Add SUSE/OBS compatibility

* Fri Apr 26 2024 Dave Dykstra <dwd@fnal.gov>> - 0.5.0-1
- Convert from python2 to python3
- Add cvmfs_search util

* Fri Aug 09 2019 Dave Dykstra <dwd@fnal.gov>> - 0.4.2-1
- Prevent crashing on new "Y" .cvmfspublished key

* Fri Apr 06 2018 Dave Dykstra <dwd@fnal.gov>> - 0.4.1-2
- Add a changelog
- Make builds more seamless on OBS
