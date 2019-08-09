# OBS expects the name %release_prefix; do not change the name
%define release_prefix 1

Summary: Inspect CernVM-FS repositories
Name: python-cvmfsutils
Version: 0.4.2
Release: %{release_prefix}%{?dist}
Source0: %{name}-%{version}.tar.gz
License: (c) 2015 CERN - BSD License
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Rene Meusel <rene.meusel@cern.ch>
Requires: python-requests >= 1.1.0 python-dateutil >= 1.4.1
Url: http://cernvm.cern.ch
BuildRequires: python-setuptools

%description
The CernVM-FS python package allows for the inspection of CernVM-FS
repositories using python. In particular to browse their file catalog
hierarchy, inspect CernVM-FS repository manifests (a.k.a. .cvmfspublished
files) and the history of named snapshots inside any CernVM-FS repository.

%prep
%setup -n %{name}-%{version} -n %{name}-%{version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)

%changelog
* Fri Aug 09 2019 Dave Dykstra <dwd@fnal.gov>> - 0.4.2-1
- Prevent crashing on new "Y" .cvmfspublished key

* Fri Apr 06 2018 Dave Dykstra <dwd@fnal.gov>> - 0.4.1-2
- Add a changelog
- Make builds more seamless on OBS
